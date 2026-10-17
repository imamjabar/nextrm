"""Enrichment boundaries: private choice, evidence, exact versions and actual outcomes."""
import json,hashlib,uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import utc_now
from app.models.relationships import *
from app.services.enrichment import feed,profile_for,insights_for,FAMILIES
from app.services.rm_seed import seed_relationships
client=TestClient(app)
def h(user='usr-dina'):return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def key():return str(uuid.uuid4())
def pid():return client.get('/v1/rm/parties',headers=h()).json()['parties'][0]['id']
def current():
    r=client.get('/v1/rm/chat/'+pid()+'/engagement',headers=h());assert r.status_code==200,r.text;return r.json()
def context(goal='Education in two years',shared=False,**extra):
    f=current();req={'base_version':f['profile']['version'],'request_key':key(),'goal':goal,'horizon':'Keep an emergency reserve accessible','interests':['goals'],'share_context':shared,**extra}
    return client.post('/v1/rm/chat/'+pid()+'/context',headers=h(),json=req),req
def feedback(action,nudge=None,**extra):
    f=current();req={'base_version':f['profile']['version'],'request_key':key(),'action':action,'nudge_id':nudge,**extra}
    return client.post('/v1/rm/chat/'+pid()+'/feedback',headers=h(),json=req),req
@pytest.fixture(autouse=True)
def active(monkeypatch):monkeypatch.setenv('NEXTRM_AI_PROVIDER','local')
def test_feed_sources_budget_and_all_catalog_rules_are_real():
    f=current();assert len(FAMILIES)==12;assert 0<len(f['nudges'])<=3
    assert sum(n['primary'] for n in f['nudges'])==1
    assert all(n['source']['hash']==hashlib.sha256(n['source']['content'].encode()).hexdigest() for n in f['nudges'])
    assert not any(x in json.dumps(f) for x in ['Internal RM note','risk score'])
    by_key={i['key']:i for i in f['insights']}
    assert all(by_key[k]['status']=='AVAILABLE' for k in ['cash_flow','spending','recurring'])
    cash=by_key['cash_flow']['values'];from decimal import Decimal
    assert Decimal(cash['difference'])==Decimal(cash['available'])-Decimal(cash['commitments'])
    assert f['insights'][1]['values']['change_percent']=='27.78'
    assert all(c['terms_status']=='Live fees and rates unavailable' for c in f['comparisons'])
    again=current();assert again['decision_id']==f['decision_id']

def test_private_goal_does_not_create_signal_and_rm_cannot_read_it():
    with SessionLocal() as db:before=db.query(Signal).count()
    r,body=context();assert r.status_code==200
    with SessionLocal() as db:assert db.query(Signal).count()==before
    assert 'Education in two years' not in client.get('/v1/rm/parties/'+pid()+'/brief',headers=h('usr-maya')).text
    assert client.get('/v1/rm/sources/'+r.json()['source_id'],headers=h('usr-maya')).status_code==403
    replay=client.post('/v1/rm/chat/'+pid()+'/context',headers=h(),json=body);assert replay.json()==r.json()
    assert client.post('/v1/rm/chat/'+pid()+'/context',headers=h(),json={**body,'goal':'Changed'}).status_code==409

def test_shared_context_visible_with_source_and_withdrawal_removes_it():
    r,_=context(shared=True);assert r.status_code==200
    brief=client.get('/v1/rm/parties/'+pid()+'/brief',headers=h('usr-maya')).json()
    assert any(x['kind']=='SHARED_CUSTOMER_CONTEXT' and x['source']['id']==r.json()['source_id'] for x in brief['facts'])
    assert context(goal='',shared=False)[0].status_code==200
    assert r.json()['source_id'] not in client.get('/v1/rm/parties/'+pid()+'/brief',headers=h('usr-maya')).text
    assert client.get('/v1/rm/sources/'+r.json()['source_id'],headers=h('usr-maya')).status_code==403

def test_goal_change_blocks_previously_displayed_action():
    f=current();n=next(n for n in f['nudges'] if n['family']=='E03')
    assert context(goal='Different goal')[0].status_code==200
    r=client.post(f"/v1/rm/chat/{pid()}/nudges/{n['id']}",headers=h(),json={'action':'REQUEST_RM','base_version':n['version'],'request_key':key(),'share_with_rm':True})
    assert r.status_code==409

def test_feedback_scope_idempotence_and_private_semantics():
    f=current();n=f['nudges'][0]
    with SessionLocal() as db:before=db.query(Signal).count()
    r,body=feedback('SNOOZE',n['id']);assert r.status_code==200
    assert client.post('/v1/rm/chat/'+pid()+'/feedback',headers=h(),json=body).json()==r.json()
    assert client.post('/v1/rm/chat/'+pid()+'/feedback',headers=h(),json={**body,'days':8}).status_code==409
    with SessionLocal() as db:assert db.query(Signal).count()==before;seed_relationships(db)
    assert any(x['reason']=='Topic snoozed by customer' for x in current()['decisions'])
    r,_=feedback('OPT_OUT');assert r.status_code==200
    f=current();assert f['profile']['commercial_allowed'] is False
    assert any(n['category']!='COMMERCIAL' for n in f['nudges'])

def test_dismiss_does_not_snooze_topic_and_recognition_cannot_be_an_rm_lead():
    with SessionLocal() as db:
        p=db.get(Party,pid());profile=profile_for(db,p);d=json.loads(profile.data_json);s=db.get(Source,d['facts']['source_id']);facts=json.loads(s.content);facts['birthday']=utc_now().astimezone(__import__('zoneinfo').ZoneInfo('Asia/Jakarta')).date().isoformat();s.content=json.dumps(facts);s.content_hash=hashlib.sha256(s.content.encode()).hexdigest();s.version+=1;db.commit()
    f=current();n=f['nudges'][0];assert feedback('DISMISS',n['id'])[0].status_code==200
    assert not current()['profile']['topic_snoozes']
    f=current();n=next(n for n in f['nudges'] if n['family']=='E02');assert not n['can_request_rm']
    assert client.post(f"/v1/rm/chat/{pid()}/nudges/{n['id']}",headers=h(),json={'action':'REQUEST_RM','base_version':n['version'],'request_key':key(),'share_with_rm':True}).status_code==422

def test_missing_birthday_never_fabricates_greeting_and_event_reseed_dedupes():
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);d=json.loads(row.data_json);s=db.get(Source,d['facts']['source_id']);facts=json.loads(s.content);facts['birthday']=None;s.content=json.dumps(facts);s.content_hash=hashlib.sha256(s.content.encode()).hexdigest();s.version+=1;db.commit()
    f=current();assert not any(x['family']=='E02' for x in f['decisions'])
    with SessionLocal() as db:before=db.query(Nudge).count();seed_relationships(db)
    current()
    with SessionLocal() as db:assert db.query(Nudge).count()==before

def unlink_bank_customer(db,party_id):
    from app.models.banking import BankCustomer
    for c in db.query(BankCustomer).filter_by(party_id=party_id):c.party_id=None

def test_unlinked_customer_gets_unavailable_insights_not_zero():
    with SessionLocal() as db:unlink_bank_customer(db,pid());db.commit()
    f=current()
    assert {i['status'] for i in f['insights']}=={'UNAVAILABLE'}
    assert all(i['values']=={} for i in f['insights'])
    assert not any(n['family'] in {'E09','E10'} for n in f['nudges'])

def test_care_and_cash_gap_suppress_commercial_without_losing_help():
    from decimal import Decimal
    from app.models.banking import BankCustomer,BankAccount
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);d=json.loads(row.data_json);event=db.get(Source,d['facts']['source_id']);facts=json.loads(event.content);facts['liquidity_requested']=True;event.content=json.dumps(facts);event.content_hash=hashlib.sha256(event.content.encode()).hexdigest();event.version+=1
        customer=db.query(BankCustomer).filter_by(party_id=p.id).one()
        for account in db.query(BankAccount).filter_by(customer_id=customer.id):account.balance=Decimal('100.00')
        db.commit()
    f=current();assert f['insights'][0]['status']=='GAP';assert any(x['family']=='E07' and x['reason']=='Financial care takes priority' for x in f['decisions']);assert f['nudges'][0]['category']=='CARE'

def test_metadata_admin_cannot_read_content_and_has_real_feedback_denominators():
    f=current();n=f['nudges'][0];feedback('EXPOSED',n['id']);feedback('HELPFUL',n['id'])
    r=client.get('/v1/rm/quality/engagement',headers=h('usr-aiadmin'));assert r.status_code==200
    assert r.json()['metrics'][0]['numerator']==1 and r.json()['metrics'][0]['denominator']==1
    assert not any(x in r.text for x in ['Dina Rahma','Preparing for school expenses','Internal RM note'])
    assert client.get('/v1/rm/quality/engagement',headers=h('usr-maya')).status_code==403
    assert client.get('/v1/rm/parties/'+pid()+'/brief',headers=h('usr-dina')).status_code==403
    for user in ['usr-maya','usr-aiadmin','usr-quality']:
        assert client.get('/v1/rm/chat/'+pid()+'/engagement',headers=h(user)).status_code==403

def test_contact_activity_is_human_recorded_deduped_and_authorized():
    p=client.get('/v1/rm/parties',headers=h('usr-maya')).json()['parties'];p=next(x for x in p if x['id']==pid())
    body={'base_version':p['version'],'request_key':key(),'channel':'MEETING','purpose':'REQUESTED_DISCUSSION','event':'PREPARED','note':'Prepared a conversation, not sent.','occurred_at':utc_now().isoformat()}
    path='/v1/rm/parties/'+pid()+'/contacts';r=client.post(path,headers=h('usr-maya'),json=body);assert r.status_code==200,r.text
    assert client.post(path,headers=h('usr-maya'),json=body).json()==r.json()
    assert client.post(path,headers=h('usr-maya'),json={**body,'note':'Other'}).status_code==409
    assert client.post(path,headers=h(),json=body).status_code==403
    assert 'Prepared a conversation, not sent.' in client.get('/v1/rm/parties/'+pid()+'/brief',headers=h('usr-maya')).text

def test_snooze_structured_outcome_preserves_original_task_and_customer_projection():
    f=current();n=next(x for x in f['nudges'] if x['family']=='E03');r=client.post(f"/v1/rm/chat/{pid()}/nudges/{n['id']}",headers=h(),json={'base_version':n['version'],'action':'REQUEST_RM','share_with_rm':True,'request_key':key()});assert r.status_code==200
    signal=next(x for x in client.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if x['id']==r.json()['signal_id'])
    s=client.post('/v1/rm/signals/'+signal['id']+'/review',headers=h('usr-maya'),json={'base_version':signal['version'],'decision':'ACCEPTED','confirmed':True}).json()
    t=client.post('/v1/rm/signals/'+s['id']+'/follow-up',headers=h('usr-maya'),json={'base_version':s['version'],'request_key':key()}).json()
    path='/v1/rm/follow-ups/'+t['id'];body={'base_version':t['version'],'request_key':key(),'action':'SNOOZE','note':'Wait for the requested date.','due_at':(utc_now()+timedelta(days=2)).isoformat()}
    r=client.post(path,headers=h('usr-maya'),json=body);assert r.status_code==200,r.text;assert r.json()['snoozed_until']
    assert client.post(path,headers=h('usr-maya'),json=body).json()==r.json()
    r=client.post(path,headers=h('usr-maya'),json={'base_version':r.json()['version'],'request_key':key(),'action':'COMPLETE','note':'Internal preparation recorded.','outcome':'NO_CURRENT_NEED'});assert r.status_code==200,r.text;assert r.json()['outcome']=='NO_CURRENT_NEED' and r.json()['status']=='DONE'
    public=client.get('/v1/rm/chat/'+pid()+'/requests',headers=h()).text;assert 'Internal preparation' not in public and 'NO_CURRENT_NEED' not in public

def test_catalog_activates_only_from_the_authorized_snapshot_and_declared_context():
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);d=json.loads(row.data_json)
        src=db.get(Source,d['facts']['source_id']);facts=json.loads(src.content);facts.update(maturity_date=(utc_now()+timedelta(days=5)).date().isoformat(),liquidity_requested=True,inactivity_days=100)
        src.content=json.dumps(facts);src.content_hash=hashlib.sha256(src.content.encode()).hexdigest();src.version+=1;db.commit()
    assert context('Travel next month',interests=['travel','goals'])[0].status_code==200
    f=current();families={x['family'] for x in f['decisions']}
    assert families>={'E01','E03','E04','E06','E07','E08','E09','E10','E11','E12'}
    with SessionLocal() as db:
        src=db.get(Source,db.query(Nudge).filter_by(party_id=pid()).first().source_id)
        original=db.query(Nudge).join(SuggestionMeta,SuggestionMeta.id==Nudge.id).filter(Nudge.party_id==pid(),SuggestionMeta.family=='E01').count()
        profile=profile_for(db,db.get(Party,pid()));d=json.loads(profile.data_json);event=db.get(Source,d['facts']['source_id']);event.version+=1;db.commit()
    current()
    with SessionLocal() as db:assert db.query(Nudge).join(SuggestionMeta,SuggestionMeta.id==Nudge.id).filter(Nudge.party_id==pid(),SuggestionMeta.family=='E01').count()==original

def test_urgent_service_comes_first_and_commercial_actions_recheck_it():
    with SessionLocal() as db:
        p=db.get(Party,pid());profile=profile_for(db,p);d=json.loads(profile.data_json);s=db.get(Source,d['facts']['source_id']);facts=json.loads(s.content);facts['liquidity_requested']=True;s.content=json.dumps(facts);s.content_hash=hashlib.sha256(s.content.encode()).hexdigest()
        from app.services.enrichment import make_source
        source=make_source(db,p,'Customer service report','My card was stolen.','CUSTOMER_MESSAGE')
        db.add(Signal(id='service-first',tenant_id=p.tenant_id,party_id=p.id,source_id=source.id,owner_id=p.owner_id,semantic_key='service-first',category='SERVICE_ISSUE',urgency='URGENT',evidence='CUSTOMER_CONFIRMED',title='Card issue',need=source.content,rationale='Customer report',uncertainty='Resolution unknown'));db.commit()
    f=current();assert f['nudges'][0]['family']=='E05';assert any(x['family']=='E07' and x['reason']=='Service care takes priority' for x in f['decisions'])

def test_no_eligible_candidate_is_useful_and_cross_subject_sources_never_leak():
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);row.data_json=json.dumps({'goal':'','facts':{},'interests':[],'snoozes':{},'share_context':False})
        for src in db.query(Source).filter_by(tenant_id=p.tenant_id,kind='APPROVED_KNOWLEDGE'):src.event_at=utc_now()-timedelta(days=35)
        unlink_bank_customer(db,p.id)
        db.commit()
    f=current();assert f['nudges']==[];assert f['insights'][0]['status']=='UNAVAILABLE'
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);other=db.query(Source).filter(Source.party_id!=p.id,Source.kind=='SYNTHETIC_LIFECYCLE').first();row.data_json=json.dumps({'goal':'','facts':{'source_id':other.id,'birthday':'1991-10-03'},'interests':[],'snoozes':{},'share_context':False});db.commit()
    assert current()['nudges']==[]

def test_category_correction_is_customer_feedback_not_a_rewritten_financial_source():
    f=current();src=f['insights'][1]['source'];path='/v1/rm/chat/'+pid()+'/category'
    body={'base_version':f['profile']['version'],'request_key':key(),'source_id':src['id'],'source_version':src['version'],'source_hash':src['hash'],'category':'School travel'}
    r=client.post(path,headers=h(),json=body);assert r.status_code==200,r.text
    assert client.post(path,headers=h(),json=body).json()==r.json()
    f=current();assert 'Customer-provided category correction: School travel' in f['insights'][1]['explanation']
    assert f['insights'][1]['source']['hash']==src['hash']
    with SessionLocal() as db:assert json.loads(db.get(Source,src['id']).content)['category']=='Transport'
    assert client.post(path,headers=h('usr-maya'),json=body).status_code==403
    assert client.post(path,headers=h(),json={**body,'request_key':key(),'source_hash':'b'*64,'base_version':f['profile']['version']}).status_code==409

def test_current_customer_context_reaches_assistant_without_internal_notes_or_rm_signal(monkeypatch):
    r,_=context('Travel fund',False,interests=['travel']);assert r.status_code==200
    import app.routers.rm as rm
    original=rm.respond;captured=[]
    def capture(message,previous,kb,party):
        captured.append(party.copy());return original(message,previous,kb,party)
    monkeypatch.setattr(rm,'respond',capture)
    conv=client.get('/v1/rm/chat/'+pid(),headers=h()).json()
    r=client.post('/v1/rm/chat/'+pid()+'/turns',headers=h(),json={'base_version':conv['version'],'request_key':key(),'message':'How does savings work?','share_with_rm':False});assert r.status_code==200
    assert captured[0]['declared_goal']=='Travel fund' and captured[0]['declared_interests']==['travel'] and 'notes' not in captured[0]
    with SessionLocal() as db:
        turn=db.get(Turn,r.json()['id']);metadata=json.loads(turn.output_json);assert metadata['context_source_id'] and metadata['context_source_hash']
    assert r.json()['signal_id'] is None

def test_commercial_refusal_does_not_block_private_education_but_blocks_shared_sales_need():
    f=current();n=next(n for n in f['nudges'] if n['family']=='E03')
    assert feedback('OPT_OUT')[0].status_code==200
    assert any(x['family']=='E03' and not x['can_request_rm'] for x in current()['nudges'])
    path=f"/v1/rm/chat/{pid()}/nudges/{n['id']}"
    assert client.post(path,headers=h(),json={'base_version':n['version'],'request_key':key(),'action':'REQUEST_RM','share_with_rm':True}).status_code==403
    assert client.post(path,headers=h(),json={'base_version':n['version'],'request_key':key(),'action':'EXPLORE','share_with_rm':False}).status_code==200

def test_anniversary_requires_a_sourced_prior_relationship_date():
    from zoneinfo import ZoneInfo
    with SessionLocal() as db:
        p=db.get(Party,pid());row=profile_for(db,p);d=json.loads(row.data_json);s=db.get(Source,d['facts']['source_id']);facts=json.loads(s.content);today=utc_now().astimezone(ZoneInfo('Asia/Jakarta')).date();facts['birthday']=None;facts['relationship_started']=today.replace(year=today.year-3).isoformat();s.content=json.dumps(facts);s.content_hash=hashlib.sha256(s.content.encode()).hexdigest();s.version+=1;db.commit()
    n=next(x for x in current()['nudges'] if x['family']=='E02');assert '3 years' in n['body'] and n['category']=='RECOGNITION' and not n['can_request_rm']
