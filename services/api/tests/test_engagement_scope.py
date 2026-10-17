"""Current RM-only product scope; historical credit runs in an explicit harness."""
import json,uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Party,Prospect,Source,Journey,Signal
c=TestClient(app)
def key():return str(uuid.uuid4())
def h(user='usr-maya',tenant='demo-bank'):return {'X-User-Id':user,'X-Tenant-Id':tenant}
@pytest.fixture(autouse=True)
def active_scope():
    pass
def person():return next(x for x in c.get('/v1/rm/parties',headers=h()).json()['parties'] if x['name']=='Dina Rahma')
def reviewed(message='I want a savings account for school expenses.'):
 p=person();conv=c.get('/v1/rm/chat/'+p['id'],headers=h('usr-dina')).json()
 turn=c.post('/v1/rm/chat/'+p['id']+'/turns',headers=h('usr-dina'),json={'message':message,'base_version':conv['version'],'request_key':key(),'share_with_rm':True}).json()
 signal=next(x for x in c.get('/v1/rm/signals',headers=h()).json()['signals'] if x['id']==turn['signal_id'])
 return c.post('/v1/rm/signals/'+signal['id']+'/review',headers=h(),json={'base_version':signal['version'],'decision':'ACCEPTED','confirmed':signal['confirmed']}).json()
def task():
 s=reviewed();r=c.post('/v1/rm/signals/'+s['id']+'/follow-up',headers=h(),json={'base_version':s['version'],'request_key':key()});assert r.status_code==200;return r.json()
def change(row,action='NOTE',note='Prepared discussion of the stated savings goal.',**kwargs):
 return c.post('/v1/rm/follow-ups/'+row['id'],headers=h(),json={'base_version':row['version'],'request_key':key(),'action':action,'note':note,**kwargs})

def test_one_business_staff_role_and_no_old_demo_personas():
 roles={x['role'] for x in c.get('/v1/auth/demo-users').json()['users']}
 assert roles=={'RM','CUSTOMER','QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'}
 for user in ['usr-other']:
  assert c.get('/v1/rm/pulse',headers=h(user)).status_code==401
  assert c.get('/v1/rm/follow-ups',headers=h(user)).status_code==401

def test_followup_source_idempotency_stale_version_and_notes():
 s=reviewed();body={'base_version':s['version'],'request_key':key()};path='/v1/rm/signals/'+s['id']+'/follow-up'
 a=c.post(path,headers=h(),json=body).json();assert a['kind']=='RM_FOLLOWUP';assert a['mode']=='HUMAN_RECORDED';assert a['source_id']==s['source_id'];assert a['status']=='PLANNED'
 assert c.post(path,headers=h(),json=body).json()['id']==a['id']
 b=change(a,due_at='2026-09-01T09:00:00+07:00').json();assert b['due_at'];assert b['history'][-1]['note'].startswith('Prepared discussion')
 assert change(a).status_code==409
 assert c.get('/v1/rm/pulse',headers=h()).json()['overdue_followups']==1

def test_unknown_response_retry_reuses_same_followup_action():
 a=task();body={'base_version':a['version'],'request_key':key(),'action':'NOTE','note':'Customer goal remains to be discussed.'};path='/v1/rm/follow-ups/'+a['id']
 first=c.post(path,headers=h(),json=body).json();again=c.post(path,headers=h(),json=body).json();assert again['version']==first['version'];assert len(again['history'])==1
 body['note']='Changed intent';assert c.post(path,headers=h(),json=body).status_code==409

def test_followup_completion_never_converts_prospect_or_opens_product():
 prospect=next(x for x in c.get('/v1/rm/prospects',headers=h()).json()['prospects'] if x['party']['name']=='Rani Kusuma')
 path='/v1/rm/prospects/'+prospect['id']
 r=c.post(path+'/needs',headers=h(),json={'base_version':prospect['version'],'need':'Customer wants a savings discussion.','confirm':True}).json()
 body={'base_version':r['version'],'request_key':key()};response=c.post(path+'/follow-up',headers=h(),json=body);assert response.status_code==200;a=response.json()
 assert c.post(path+'/follow-up',headers=h(),json=body).json()['id']==a['id']
 a=change(a,'START','RM began preparation.').json();a=change(a,'COMPLETE','RM preparation completed; customer continues separately.').json();assert a['status']=='DONE'
 detail=c.get('/v1/rm/parties/'+prospect['party']['id'],headers=h()).json();assert detail['party']['relationship']=='NO_MATCH_IN_AVAILABLE_DATA';assert detail['party']['customer_ref'] is None
 assert detail['journeys'][0]['kind']=='RM_FOLLOWUP';assert 'not product opening' in a['completion_rule']
 projected=next(p for p in c.get('/v1/rm/prospects',headers=h()).json()['prospects'] if p['id']==prospect['id'])
 assert projected['priority_tier']=='FOLLOWUP_RECORDED' and projected['followup_id']==a['id'] and not projected['hot_lead']
 assert c.post(path+'/needs',headers=h(),json={'base_version':projected['version'],'need':'Rewrite completed work','confirm':True}).status_code==409

def test_customer_cannot_inspect_private_followup_notes():
 a=task();a=change(a,note='Internal preparation note: clarify the date.').json()
 assert c.get('/v1/rm/follow-ups/'+a['id'],headers=h('usr-dina')).status_code==403
 public=c.get('/v1/rm/chat/'+a['party_id']+'/progress',headers=h('usr-dina')).json()['journeys'][0]
 assert 'Internal preparation note' not in json.dumps(public);assert 'Draft only' not in public['draft'];assert public['signal_id'] is None

def test_restriction_blocks_commercial_task_but_preserves_help():
 a=task();p=person();r=c.post('/v1/rm/parties/'+p['id']+'/preferences',headers=h('usr-dina'),json={'base_version':p['version'],'commercial_allowed':False,'reason':'No commercial contact requested.'});assert r.status_code==200
 assert change(a,'START').status_code==403;assert change(a,'NOTE').status_code==200
 s=reviewed('My recipient cannot see my transfer. Please help.');r=c.post('/v1/rm/signals/'+s['id']+'/follow-up',headers=h(),json={'base_version':s['version'],'request_key':key()});assert r.status_code==200
 assert change(r.json(),'START').status_code==200
 assert c.get('/v1/rm/destinations',headers=h('usr-dina')).status_code==200

def test_foreign_subject_source_and_tenant_denials():
 a=task();assert c.get('/v1/rm/follow-ups/'+a['id'],headers=h('usr-maya','other-tenant')).status_code==403
 with SessionLocal() as db:
  row=db.get(Journey,a['id']);other=db.query(Source).filter(Source.party_id.isnot(None),Source.party_id!=row.party_id).first();row.source_id=other.id;db.commit()
 assert c.get('/v1/rm/follow-ups/'+a['id'],headers=h()).status_code==409
 assert c.get('/v1/rm/pulse',headers=h()).status_code==409

def test_malformed_due_and_missing_completion_reason_rejected():
 a=task();assert change(a,due_at='2026-10-01T09:00:00').status_code==422
 assert change(a,'COMPLETE',note='').status_code==422
 assert change(a,due_at='not a date').status_code==422

def test_menu_configuration_is_institution_scoped_and_fail_closed(monkeypatch):
 data=c.get('/v1/rm/destinations',headers=h('usr-dina')).json();assert all(x['href'] is None and x['status']=='NOT_CONFIGURED' for x in data['destinations'])
 monkeypatch.setenv('NEXTRM_MENU_LINKS_JSON',json.dumps({'other-bank':{'loan':'https://other.invalid/loans'},'demo-bank':{'loan':'https://bank.example.invalid/products/loans'}}))
 loan=next(x for x in c.get('/v1/rm/destinations',headers=h('usr-dina')).json()['destinations'] if x['key']=='loan');assert loan['href']=='https://bank.example.invalid/products/loans'
 monkeypatch.setenv('NEXTRM_MENU_LINKS_JSON','{"demo-bank":{"loan":"javascript:alert(1)"}}');assert c.get('/v1/rm/destinations',headers=h()).status_code==503
 assert c.get('/v1/rm/destinations',headers=h('usr-quality')).status_code==403

def test_loan_chat_routes_to_menu_not_credit_decision():
 p=person();conv=c.get('/v1/rm/chat/'+p['id'],headers=h('usr-dina')).json()
 r=c.post('/v1/rm/chat/'+p['id']+'/turns',headers=h('usr-dina'),json={'message':'I want a loan. Can you approve it?','base_version':conv['version'],'request_key':key(),'share_with_rm':True});assert r.status_code==200
 t=r.json();assert t['route']=='LOAN';assert t['model']=='local-governed-engine-v1.5';assert 'separate loan menu' in t['answer'];assert 'NextRM does not submit or approve a loan' in t['answer']
 assert {x['name'] for x in t['tools']}=={'read_approved_knowledge','read_permitted_customer_context'}
 with SessionLocal() as db:assert db.query(Journey).count()==0

def test_missing_menu_knowledge_fails_before_committing_chat_turn():
 from app.models.relationships import Turn
 p=person();conv=c.get('/v1/rm/chat/'+p['id'],headers=h('usr-dina')).json()
 with SessionLocal() as db:db.query(Source).filter(Source.id.like('%KB-loan')).delete(synchronize_session=False);db.commit()
 r=c.post('/v1/rm/chat/'+p['id']+'/turns',headers=h('usr-dina'),json={'message':'I want a loan.','base_version':conv['version'],'request_key':key(),'share_with_rm':True});assert r.status_code==503
 with SessionLocal() as db:assert db.query(Turn).count()==0

def test_quality_reports_actual_menu_configuration(monkeypatch):
 monkeypatch.setenv('NEXTRM_MENU_LINKS_JSON','{"demo-bank":{"loan":"https://bank.example.invalid/loans"}}')
 health=c.get('/v1/rm/quality',headers=h('usr-aiadmin')).json()['health'];assert next(x for x in health if x['name']=='Product menus / POI')['status']=='CONFIGURED_NOT_VERIFIED'
 monkeypatch.setenv('NEXTRM_MENU_LINKS_JSON','{"demo-bank":{"loan":"javascript:bad"}}')
 health=c.get('/v1/rm/quality',headers=h('usr-aiadmin')).json()['health'];assert next(x for x in health if x['name']=='Product menus / POI')['status']=='UNAVAILABLE'


def test_latency_summary_does_not_report_fastest_of_two_as_p95():
 from app.services.rm_evaluations import percentile
 assert percentile([592,836],.5)==714
 assert percentile([592,836],.95)==836
 assert percentile([], .95) is None
 assert percentile([40,10,30,20], .5)==25
