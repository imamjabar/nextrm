"""Customer-choice lineage and permission gates, not click-to-sale attribution."""
import hashlib, json, uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import utc_now
from app.models.relationships import Nudge, Signal, Source, Party, Journey, ReviewEvent, Prospect
from app.services.rm_seed import seed_relationships

client=TestClient(app)
def headers(user='usr-dina'): return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def key(): return str(uuid.uuid4())
def pid(): return next(p['id'] for p in client.get('/v1/rm/parties',headers=headers()).json()['parties'] if p['name']=='Dina Rahma')
def get_nudge():
    r=client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()); assert r.status_code==200
    return r.json()['nudges'][0]
def act(n,action='REQUEST_RM',share=True,**overrides):
    body={'base_version':n['version'],'request_key':key(),'action':action,'share_with_rm':share,**overrides}
    return client.post(f"/v1/rm/chat/{n['party_id']}/nudges/{n['id']}",headers=headers(),json=body)
@pytest.fixture(autouse=True)
def active_scope(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER','local')

def test_suggestion_has_authorized_person_and_approved_source_not_private_notes():
    n=get_nudge();assert 'school' in n['title'].lower();assert n['mode']=='SIMULATED'
    assert n['source']['kind']=='SYNTHETIC_CUSTOMER_CONTEXT';assert n['knowledge']['kind']=='APPROVED_KNOWLEDGE'
    assert n['source']['hash']==hashlib.sha256(n['source']['content'].encode()).hexdigest()
    assert 'Internal RM note' not in json.dumps(n);assert n['signal_id'] is None

def test_exploring_privately_never_creates_signal_or_purchase_interest():
    n=get_nudge()
    with SessionLocal() as db:before=db.query(Signal).count()
    r=act(n,'EXPLORE',False);assert r.status_code==200;assert r.json()['state']=='EXPLORED';assert r.json()['signal_id'] is None
    assert get_nudge()['state']=='EXPLORED'
    with SessionLocal() as db:assert db.query(Signal).count()==before;assert db.query(Journey).count()==0

def test_explicit_shared_request_creates_one_reviewable_sourced_need_and_idempotent_receipt():
    n=get_nudge();request=key();r=act(n,request_key=request);assert r.status_code==200
    assert act(n,request_key=request).json()['signal_id']==r.json()['signal_id']
    with SessionLocal() as db:
        s=db.get(Signal,r.json()['signal_id']);source=db.get(Source,s.source_id)
        assert s.confirmed and s.review=='PROPOSED' and s.workflow=='NEW'
        assert source.kind=='CUSTOMER_MESSAGE' and 'request for a conversation' in source.content
        assert source.content_hash==hashlib.sha256(source.content.encode()).hexdigest()
        assert n['source']['id'] in s.rationale and n['knowledge']['id'] in s.rationale
        assert db.query(Signal).filter_by(semantic_key='NUDGE-'+n['id']).count()==1
        assert db.query(ReviewEvent).filter_by(resource_id=n['id']).count()==1
        assert db.query(Journey).count()==0
    signals=client.get('/v1/rm/signals',headers=headers('usr-maya')).json()['signals']
    signal=next(s for s in signals if s['id']==r.json()['signal_id'])
    assert signal['display_label']=='Potential opportunity'
    assert act(n,request_key=request,action='DISMISS').status_code==409
    assert act(r.json()).status_code==409

def test_request_sharing_off_fails_without_side_effect_and_dismissal_survives_reseed():
    n=get_nudge();assert act(n,share=False).status_code==422
    assert get_nudge()['state']=='AVAILABLE'
    r=act(n,'DISMISS',False);assert r.status_code==200
    with SessionLocal() as db:seed_relationships(db);assert db.get(Nudge,n['id']).state=='DISMISSED'
    assert client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()).json()['nudges']==[]

def test_changed_base_version_and_concurrent_request_are_conflicts_not_duplicates():
    n=get_nudge();r=act(n,'EXPLORE',False);assert r.status_code==200
    assert act(n).status_code==409
    with SessionLocal() as db:assert db.query(Signal).filter_by(semantic_key='NUDGE-'+n['id']).count()==0
    assert act(r.json()).status_code==200

def test_optout_after_display_suppresses_commercial_suggestion_and_old_action():
    n=get_nudge()
    with SessionLocal() as db:p=db.get(Party,n['party_id']);p.contact='RESTRICTED';p.version+=1;db.commit()
    assert act(n).status_code==409
    assert client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()).json()['nudges']==[]
    # Service help still works and is shared only on explicit choice.
    conv=client.get(f'/v1/rm/chat/{pid()}',headers=headers()).json()
    r=client.post(f'/v1/rm/chat/{pid()}/turns',headers=headers(),json={'message':'My recipient cannot see a transfer','base_version':conv['version'],'request_key':key(),'share_with_rm':True})
    assert r.status_code==200 and r.json()['route']=='SERVICE' and r.json()['signal_id']

def test_urgent_service_suppresses_sales_nudge_until_help_work_is_addressed():
    n=get_nudge()
    with SessionLocal() as db:
        src=Source(id='urgent-src',tenant_id='demo-bank',party_id=n['party_id'],kind='CUSTOMER_MESSAGE',title='Service request',content='My card is stolen',content_hash=hashlib.sha256(b'My card is stolen').hexdigest(),mode='SIMULATED')
        db.add(src);db.flush()
        db.add(Signal(id='urgent',tenant_id='demo-bank',party_id=n['party_id'],source_id=src.id,owner_id='usr-maya',semantic_key='urgent',category='SERVICE_ISSUE',urgency='URGENT',evidence='OBSERVED',title='Card issue',need='Check card',rationale='Customer request',uncertainty='Status unconfirmed'));db.commit()
    assert act(n).status_code==409
    assert client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()).json()['nudges']==[]

@pytest.mark.parametrize('user',['usr-quality','usr-aiadmin','usr-maya'])
def test_suggestions_do_not_bypass_role_scope(user):
    n=get_nudge();path=f"/v1/rm/chat/{n['party_id']}/nudges"
    assert client.get(path,headers=headers(user)).status_code==403
    assert client.post(path+'/'+n['id'],headers=headers(user),json={'base_version':n['version'],'request_key':key(),'action':'REQUEST_RM','share_with_rm':True}).status_code==403

def test_other_customer_business_and_foreign_source_denied():
    n=get_nudge()
    with SessionLocal() as db:
        other=db.query(Party).filter_by(tenant_id='demo-bank',name='Aditya Pratama').one()
        assert client.get(f'/v1/rm/chat/{other.id}/nudges',headers=headers()).status_code==404
        org=db.query(Party).filter_by(tenant_id='demo-bank',kind='ORGANIZATION').first()
        assert client.get(f'/v1/rm/chat/{org.id}/nudges',headers=headers('usr-maya')).status_code==403
        row=db.get(Nudge,n['id']);row.source_id=db.query(Source).filter_by(party_id=other.id).first().id;db.commit()
    assert act(n).status_code==409
    assert client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()).status_code==409

@pytest.mark.parametrize('age',[31,-1])
def test_stale_or_future_context_cannot_create_new_request(age):
    n=get_nudge()
    with SessionLocal() as db:db.get(Source,n['source']['id']).event_at=utc_now()-timedelta(days=age);db.commit()
    assert act(n).status_code==409
    assert client.get(f'/v1/rm/chat/{pid()}/nudges',headers=headers()).json()['nudges']==[]

def test_nudge_handoff_review_and_done_preserve_customer_projection():
    n=get_nudge();r=act(n).json()
    signal=next(s for s in client.get('/v1/rm/signals',headers=headers('usr-maya')).json()['signals'] if s['id']==r['signal_id'])
    s=client.post('/v1/rm/signals/'+signal['id']+'/review',headers=headers('usr-maya'),json={'base_version':signal['version'],'decision':'ACCEPTED','confirmed':True}).json()
    t=client.post('/v1/rm/signals/'+s['id']+'/follow-up',headers=headers('usr-maya'),json={'base_version':s['version'],'request_key':key()}).json()
    client.post('/v1/rm/follow-ups/'+t['id'],headers=headers('usr-maya'),json={'base_version':t['version'],'request_key':key(),'action':'COMPLETE','note':'Staff-only call preparation details.'})
    public=client.get(f'/v1/rm/chat/{pid()}/progress',headers=headers()).json()
    assert public['journeys'][0]['status']=='DONE';assert 'Staff-only' not in json.dumps(public)
    assert 'product application or purchase' in public['journeys'][0]['need']
    with SessionLocal() as db:assert db.get(Party,pid()).relationship=='EXISTING_CUSTOMER'

def test_prospect_order_explains_gates_and_promotes_reviewed_needs():
    rows=client.get('/v1/rm/prospects',headers=headers('usr-maya')).json()['prospects']
    assert all(r['priority_method']=='ACQ-1' and r['priority_reason'] and r['next_action'] for r in rows)
    assert rows[0]['priority_tier']=='REVIEW_FIRST'
    assert {r['priority_tier'] for r in rows} >= {'CONTACT_RESTRICTED','IDENTITY_REVIEW','EXISTING_RELATIONSHIP'}
    rani=next(r for r in rows if r['party']['name']=='Rani Kusuma')
    response=client.post('/v1/rm/prospects/'+rani['id']+'/needs',headers=headers('usr-maya'),json={'base_version':rani['version'],'need':rani['need'],'confirm':True});assert response.status_code==200
    ranked=client.get('/v1/rm/prospects',headers=headers('usr-maya')).json()['prospects']
    assert ranked[0]['id']==rani['id'] and ranked[0]['priority_tier']=='READY_FOR_DISCUSSION'
    with SessionLocal() as db:db.get(Source,rani['source']['id']).event_at=utc_now()-timedelta(days=31);db.commit()
    ranked=client.get('/v1/rm/prospects',headers=headers('usr-maya')).json()['prospects']
    assert next(r for r in ranked if r['id']==rani['id'])['priority_tier']=='SOURCE_REVIEW'
    assert ranked[0]['id']!=rani['id']
    stale_review=client.post('/v1/rm/prospects/'+rani['id']+'/needs',headers=headers('usr-maya'),json={'base_version':response.json()['version'],'need':rani['need'],'confirm':True})
    assert stale_review.status_code==409
    stale_follow=client.post('/v1/rm/prospects/'+rani['id']+'/follow-up',headers=headers('usr-maya'),json={'base_version':response.json()['version'],'request_key':key()})
    assert stale_follow.status_code==409
    home=client.get('/v1/rm/home',headers=headers('usr-maya')).json()
    assert home['prospect_preview'][0]['id']==ranked[0]['id']
