"""Current three-account contract, shared-request lifecycle and territory gates."""
import hashlib,json,uuid
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import utc_now
from app.models.relationships import Party,Source,Signal,Journey,QualityGrant,ContactPreference
c=TestClient(app)
def h(user='usr-dina',tenant='demo-bank'):return {'X-User-Id':user,'X-Tenant-Id':tenant}
def key():return str(uuid.uuid4())
def person():return c.get('/v1/rm/parties',headers=h()).json()['parties'][0]
def chat(message,share=True):
 p=person();path='/v1/rm/chat/'+p['id'];conv=c.get(path,headers=h());assert conv.status_code==200
 r=c.post(path+'/turns',headers=h(),json={'base_version':conv.json()['version'],'request_key':key(),'message':message,'share_with_rm':share});assert r.status_code==200
 return r.json()
@pytest.fixture(autouse=True)
def active(monkeypatch):
 monkeypatch.setenv('NEXTRM_AI_PROVIDER','local')

@pytest.mark.parametrize('user',['usr-maya','usr-aiadmin','usr-quality'])
def test_staff_cannot_use_any_customer_phone_endpoint(user):
 p=person();path='/v1/rm/chat/'+p['id']
 for suffix in ['','/progress','/requests','/nudges']:assert c.get(path+suffix,headers=h(user)).status_code==403
 for suffix,body in [('/turns',{'base_version':1,'request_key':key(),'message':'I want savings','share_with_rm':True}),('/nudges/not-real',{'base_version':1,'request_key':key(),'action':'REQUEST_RM','share_with_rm':True})]:
  assert c.post(path+suffix,headers=h(user),json=body).status_code==403
 assert c.post('/v1/rm/parties/'+p['id']+'/preferences',headers=h(user),json={'base_version':p['version'],'commercial_allowed':False,'reason':'Attempted impersonation'}).status_code==403

@pytest.mark.parametrize('user',['usr-dina','usr-aiadmin','usr-quality'])
def test_other_accounts_cannot_enter_rm_surfaces(user):
 for path in ['home','signals','prospects','pulse','follow-ups']:assert c.get('/v1/rm/'+path,headers=h(user)).status_code==403

@pytest.mark.parametrize('user',['usr-maya','usr-dina'])
def test_customer_rm_cannot_read_quality_or_queue_evaluations_even_with_old_grant(user):
 with SessionLocal() as db:
  db.add(QualityGrant(id='old-'+user,tenant_id='demo-bank',user_id=user,content=True,active=True,purpose='Historical grant'));db.commit()
 assert c.get('/v1/rm/quality',headers=h(user)).status_code==403
 assert c.post('/v1/rm/evaluations',headers=h(user),json={'request_key':key()}).status_code==403

@pytest.mark.parametrize('message',['How does a term deposit work?','What is a savings account?','How do card payments work?','What does pending mean for a transfer?','What should I do if my card is stolen?','What does a relationship manager do?','I am just researching savings, not interested in opening anything.'])
def test_general_help_does_not_create_rm_work(message):
 turn=chat(message);assert turn['status']=='COMPLETED';assert turn['signal_id'] is None;assert turn['sharing_status']=='HELP_ONLY'
 assert c.get('/v1/rm/chat/'+person()['id']+'/requests',headers=h()).json()['requests']==[]

@pytest.mark.parametrize('message',['I would like to speak to my RM about my savings goal.','I would like human help with a banking service issue.','My recipient cannot see a transfer.','I want to save for school expenses.'])
def test_explicit_request_creates_customer_visible_source_but_no_task_until_review(message):
 p=person()
 req=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':message,'method':'PHONE_CALL','window':'MORNING'})
 assert req.status_code==200
 requests=c.get('/v1/rm/chat/'+p['id']+'/requests',headers=h()).json()['requests']
 assert requests[0]['message']==message and requests[0]['status']=='AWAITING_REVIEW'
 with SessionLocal() as db:assert db.query(Journey).count()==0

@pytest.mark.parametrize('message',['I do not want to speak to my RM about savings.','Do not ask my RM to contact me.','No need to arrange a discussion about deposits.','Can an RM help with savings? I am only researching, no follow-up please.'])
def test_declining_human_followup_never_creates_a_request(message):
 turn=chat(message);assert turn['signal_id'] is None

def test_own_subject_and_forged_role_headers_do_not_expand_access():
 with SessionLocal() as db:other=db.query(Party).filter_by(name='Aditya Pratama',tenant_id='demo-bank').one().id
 assert c.get('/v1/rm/chat/'+other+'/requests',headers=h()).status_code==404
 assert c.get('/v1/rm/home',headers={**h(),'X-Role':'RM'}).status_code==403
 assert c.get('/v1/rm/quality',headers={**h('usr-maya'),'X-Role':'INSTITUTION_AI_ADMIN'}).status_code==403

def test_shared_request_progress_uses_original_statement_not_staff_edits_or_notes():
 message='I want to save for school expenses.';p=person()
 req=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':message,'method':'PHONE_CALL','window':'MORNING'}).json()
 signal=next(s for s in c.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if s['id']==req['id'])
 reviewed=c.post('/v1/rm/signals/'+signal['id']+'/review',headers=h('usr-maya'),json={'base_version':signal['version'],'decision':'EDITED','need':'Internal staff interpretation','reason':'Private RM rationale','confirmed':False}).json()
 path='/v1/rm/chat/'+p['id']+'/requests'
 assert c.get(path,headers=h()).json()['requests'][0]['status']=='REVIEWED'
 task=c.post('/v1/rm/signals/'+signal['id']+'/follow-up',headers=h('usr-maya'),json={'base_version':reviewed['version'],'request_key':key()}).json()
 assert c.get(path,headers=h()).json()['requests'][0]['status']=='FOLLOWUP_PLANNED'
 for action,status in [('START','RM_PREPARING'),('COMPLETE','RM_WORK_RECORDED')]:
  r=c.post('/v1/rm/follow-ups/'+task['id'],headers=h('usr-maya'),json={'base_version':task['version'],'request_key':key(),'action':action,'note':'Private RM activity note'});assert r.status_code==200;task=r.json()
  public=c.get(path,headers=h()).json();assert public['requests'][0]['status']==status and public['requests'][0]['message']==message
  assert not any(v in json.dumps(public) for v in ['Internal staff interpretation','Private RM','Draft only'])
 assert c.post('/v1/rm/signals/'+signal['id']+'/review',headers=h('usr-maya'),json={'base_version':next(s['version'] for s in c.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if s['id']==signal['id']),'decision':'ACCEPTED'}).status_code==409

def test_requested_service_survives_refusal_and_private_conversation_stays_private():
 p=person();c.post('/v1/rm/parties/'+p['id']+'/preferences',headers=h(),json={'base_version':p['version'],'commercial_allowed':False,'reason':'No commercial outreach'})
 assert chat('I want to save for school expenses.')['signal_id'] is None
 assert chat('I would like human help with a banking service issue.')['signal_id']
 private=chat('My card is stolen.',share=False);assert private['signal_id'] is None and private['sharing_status']=='PRIVATE'

def test_hot_discussion_requires_unmodified_reviewed_optin_and_current_gates():
 rows=c.get('/v1/rm/prospects',headers=h('usr-maya')).json()['prospects'];rani=next(p for p in rows if p['party']['name']=='Rani Kusuma');assert not rani['hot_lead']
 path='/v1/rm/prospects/'+rani['id']+'/needs'
 reviewed=c.post(path,headers=h('usr-maya'),json={'base_version':rani['version'],'need':rani['need'],'confirm':True}).json();assert reviewed['hot_lead']
 edited=c.post(path,headers=h('usr-maya'),json={'base_version':reviewed['version'],'need':'A different staff interpretation','confirm':True}).json();assert not edited['hot_lead']
 restored=c.post(path,headers=h('usr-maya'),json={'base_version':edited['version'],'need':rani['need'],'confirm':True}).json();assert restored['hot_lead']
 with SessionLocal() as db:db.get(Party,rani['party']['id']).contact='RESTRICTED';db.commit()
 updated=next(p for p in c.get('/v1/rm/prospects',headers=h('usr-maya')).json()['prospects'] if p['id']==rani['id']);assert not updated['hot_lead']

def test_customer_requests_fail_closed_on_foreign_source():
 p=person()
 req=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I want to save for school expenses.','method':'PHONE_CALL','window':'MORNING'}).json()
 with SessionLocal() as db:
  signal=db.get(Signal,req['id']);foreign=db.query(Source).filter(Source.party_id.isnot(None),Source.party_id!=signal.party_id).first();signal.source_id=foreign.id;db.commit()
 r=c.get('/v1/rm/chat/'+p['id']+'/requests',headers=h());assert r.status_code==409

@pytest.mark.parametrize('payload',[[],{'at':'invalid'},{'at':None},{'at':float('inf')}])
def test_invalid_worker_probe_is_unknown_not_api_failure(monkeypatch,tmp_path,payload):
 path=tmp_path/'health.json';path.write_text(json.dumps(payload));monkeypatch.setenv('NEXTRM_WORKER_HEALTH_FILE',str(path))
 r=c.get('/v1/rm/quality',headers=h('usr-aiadmin'));assert r.status_code==200
 assert next(item for item in r.json()['health'] if item['name']=='Evaluation worker')['status']=='NOT_OBSERVED'

def test_future_worker_probe_is_not_current_health(monkeypatch,tmp_path):
 with SessionLocal() as db:digest=hashlib.sha256(str(db.get_bind().engine.url).encode()).hexdigest()[:12]
 path=tmp_path/'health.json';path.write_text(json.dumps({'at':utc_now().timestamp()+60,'database_fingerprint':digest}));monkeypatch.setenv('NEXTRM_WORKER_HEALTH_FILE',str(path))
 assert next(item for item in c.get('/v1/rm/quality',headers=h('usr-aiadmin')).json()['health'] if item['name']=='Evaluation worker')['status']=='NOT_OBSERVED'

def test_explicit_request_contact_preference_recorded_and_visible_to_rm():
 p=person()
 r0=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I would like to speak to my RM about my savings goal.','method':'PHONE_CALL','window':'MORNING'})
 assert r0.status_code==200;sig_id=r0.json()['id']
 url=f'/v1/rm/chat/{p["id"]}/requests/{sig_id}/preference'
 r=c.post(url,headers=h(),json={'request_key':key(),'method':'VIDEO_CALL','window':'AFTERNOON'})
 assert r.status_code==200
 res=r.json();assert res['id']==sig_id and res['contact_method']=='VIDEO_CALL' and res['contact_window']=='AFTERNOON'
 reqs=c.get(f'/v1/rm/chat/{p["id"]}/requests',headers=h()).json()['requests']
 item=next(x for x in reqs if x['id']==sig_id)
 assert item['contact_method']=='VIDEO_CALL' and item['contact_window']=='AFTERNOON'
 detail=c.get(f'/v1/rm/parties/{p["id"]}',headers=h('usr-maya')).json()
 sig=next(x for x in detail['signals'] if x['id']==sig_id)
 assert sig['contact_method']=='VIDEO_CALL' and sig['contact_window']=='AFTERNOON'

def test_contact_preference_replay_and_supersede():
 p=person()
 r0=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I want to save for school expenses.','method':'PHONE_CALL','window':'MORNING'})
 assert r0.status_code==200;sig_id=r0.json()['id']
 url=f'/v1/rm/chat/{p["id"]}/requests/{sig_id}/preference'
 k1=key()
 r1=c.post(url,headers=h(),json={'request_key':k1,'method':'PHONE_CALL','window':'MORNING'});assert r1.status_code==200
 with SessionLocal() as db:assert db.query(ContactPreference).filter_by(signal_id=sig_id).count()==2
 k2=key()
 r2=c.post(url,headers=h(),json={'request_key':k2,'method':'EMAIL','window':'ANY_TIME'});assert r2.status_code==200
 assert r2.json()['contact_method']=='EMAIL' and r2.json()['contact_window']=='ANY_TIME'
 reqs=c.get(f'/v1/rm/chat/{p["id"]}/requests',headers=h()).json()['requests']
 item=next(x for x in reqs if x['id']==sig_id)
 assert item['contact_method']=='EMAIL' and item['contact_window']=='ANY_TIME'
 with SessionLocal() as db:assert db.query(ContactPreference).filter_by(signal_id=sig_id).count()==3
 r_replay=c.post(url,headers=h(),json={'request_key':k1,'method':'PHONE_CALL','window':'MORNING'});assert r_replay.status_code==200
 with SessionLocal() as db:assert db.query(ContactPreference).filter_by(signal_id=sig_id).count()==3
 r_conflict=c.post(url,headers=h(),json={'request_key':k1,'method':'VIDEO_CALL','window':'AFTERNOON'});assert r_conflict.status_code==409

def test_contact_preference_permissions():
 p=person()
 r0=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I want to save for school expenses.','method':'PHONE_CALL','window':'MORNING'})
 sig_id=r0.json()['id']
 url=f'/v1/rm/chat/{p["id"]}/requests/{sig_id}/preference'
 r_other=c.post(url,headers=h('usr-aditya'),json={'request_key':key(),'method':'PHONE_CALL','window':'MORNING'})
 assert r_other.status_code in {403,404}
 r_rm=c.post(url,headers=h('usr-maya'),json={'request_key':key(),'method':'PHONE_CALL','window':'MORNING'})
 assert r_rm.status_code==403

def test_contact_preference_rejected_signal_closed():
 p=person()
 r0=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I would like human help with a banking service issue.','method':'PHONE_CALL','window':'MORNING'})
 sig_id=r0.json()['id']
 sigs=c.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals']
 s=next(x for x in sigs if x['id']==sig_id)
 rev=c.post(f'/v1/rm/signals/{sig_id}/review',headers=h('usr-maya'),json={'base_version':s['version'],'decision':'REJECTED','reason':'Not eligible'})
 assert rev.status_code==200
 url=f'/v1/rm/chat/{p["id"]}/requests/{sig_id}/preference'
 r=c.post(url,headers=h(),json={'request_key':key(),'method':'PHONE_CALL','window':'MORNING'})
 assert r.status_code==409

def test_post_requests_creates_request_visible_in_get_and_rm_surfaces():
 p=person();k=key();msg='Can you help me plan savings for my tuition next semester?'
 r=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':k,'message':msg,'method':'PHONE_CALL','window':'MORNING'})
 assert r.status_code==200;res=r.json()
 assert res['message']==msg and res['contact_method']=='PHONE_CALL' and res['contact_window']=='MORNING' and res['status']=='AWAITING_REVIEW'
 reqs=c.get(f'/v1/rm/chat/{p["id"]}/requests',headers=h()).json()['requests']
 item=next(x for x in reqs if x['id']==res['id'])
 assert item['message']==msg and item['contact_method']=='PHONE_CALL' and item['contact_window']=='MORNING'
 sigs=c.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals']
 rm_sig=next(s for s in sigs if s['id']==res['id'])
 assert rm_sig['need']==msg and rm_sig['contact_method']=='PHONE_CALL' and rm_sig['contact_window']=='MORNING'
 assert rm_sig['origin']=='REQUEST' and rm_sig['group']=='ASKED'
 party_view=c.get(f'/v1/rm/parties/{p["id"]}',headers=h('usr-maya')).json()
 p_sig=next(s for s in party_view['signals'] if s['id']==res['id'])
 assert p_sig['need']==msg and p_sig['contact_method']=='PHONE_CALL' and p_sig['contact_window']=='MORNING'

def test_customer_request_credential_redaction():
 p=person();msg='Please help me, my PIN is 123456 and my card is blocked'
 r=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':msg,'method':'EMAIL','window':'ANY_TIME'})
 assert r.status_code==200;res=r.json()
 assert '123456' not in res['message'] and '[redacted]' in res['message']
 with SessionLocal() as db:
  sig=db.get(Signal,res['id']);src=db.get(Source,sig.source_id)
  assert '123456' not in sig.need and '[redacted]' in sig.need
  assert '123456' not in src.content and '[redacted]' in src.content

def test_customer_request_category_service_issue_vs_guidance():
 p=person()
 r_srv=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'My debit card payment failed and money was deducted','method':'PHONE_CALL','window':'MORNING'})
 assert r_srv.status_code==200
 with SessionLocal() as db:assert db.get(Signal,r_srv.json()['id']).category=='SERVICE_ISSUE'
 r_plain=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json={'request_key':key(),'message':'I would like guidance on managing my savings better','method':'BRANCH_MEETING','window':'AFTERNOON'})
 assert r_plain.status_code==200
 with SessionLocal() as db:assert db.get(Signal,r_plain.json()['id']).category=='GUIDANCE'

def test_customer_request_idempotency_and_conflict():
 p=person();k=key();body={'request_key':k,'message':'I need advice on savings','method':'PHONE_CALL','window':'MORNING'}
 r1=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json=body);assert r1.status_code==200
 with SessionLocal() as db:cnt1=db.query(Signal).count();pref_cnt1=db.query(ContactPreference).count()
 r2=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json=body);assert r2.status_code==200 and r2.json()['id']==r1.json()['id']
 with SessionLocal() as db:assert db.query(Signal).count()==cnt1 and db.query(ContactPreference).count()==pref_cnt1
 body_conflict={'request_key':k,'message':'Different message content','method':'PHONE_CALL','window':'MORNING'}
 assert c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json=body_conflict).status_code==409

def test_customer_request_role_and_tenancy_security():
 p=person();body={'request_key':key(),'message':'I want to talk to my RM','method':'PHONE_CALL','window':'MORNING'}
 assert c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h('usr-maya'),json=body).status_code==403
 assert c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h('usr-aditya'),json=body).status_code in {403,404}

def test_customer_request_allowed_when_contact_restricted():
 p=person();c.post(f'/v1/rm/parties/{p["id"]}/preferences',headers=h(),json={'base_version':p['version'],'commercial_allowed':False,'reason':'Customer requested no commercial marketing'})
 body={'request_key':key(),'message':'I still want to talk about my mortgage account','method':'PHONE_CALL','window':'MORNING'}
 r=c.post(f'/v1/rm/chat/{p["id"]}/requests',headers=h(),json=body)
 assert r.status_code==200 and r.json()['message']==body['message']

def test_captured_chat_turn_vs_customer_request():
 turn=chat('Talk to my RM about my credit card',share=True)
 assert turn['status']=='COMPLETED' and turn['rm_suggested'] is True and turn['signal_id'] is not None
 sig_id=turn['signal_id']
 sigs=c.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals']
 rm_sig=next(s for s in sigs if s['id']==sig_id)
 assert rm_sig['group']=='SPOTTED' and rm_sig['origin']=='CHAT' and rm_sig['category']!='SERVICE_ISSUE' and rm_sig['title']=='Card conversation'
 p=person()
 cust_reqs=c.get(f'/v1/rm/chat/{p["id"]}/requests',headers=h()).json()['requests']
 assert not any(x['id']==sig_id for x in cust_reqs)
 turn_info=chat('What is a savings account?')
 assert turn_info['rm_suggested'] is False
