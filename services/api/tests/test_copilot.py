import json,uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Party,Turn,ReviewEvent
from app.services.assistant import engine,copilot
from app.services.assistant.engine import ProviderFailure
c=TestClient(app)
def h(user='usr-maya'):return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def dina():return next(x for x in c.get('/v1/rm/parties',headers=h()).json()['parties'] if x['name']=='Dina Rahma')
def ask(message,user='usr-maya',**extra):return c.post('/v1/rm/copilot/turns',headers=h(user),json={'message':message,**extra})
def analyst(message,user='usr-aiadmin',**extra):return c.post('/v1/rm/quality-assistant/turns',headers=h(user),json={'message':message,**extra})
def live(monkeypatch,*answers):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER','vertex');monkeypatch.setenv('GOOGLE_CLOUD_PROJECT','test');monkeypatch.setenv('GOOGLE_CLOUD_LOCATION','asia-southeast1');monkeypatch.setenv('GEMINI_MODEL','gemini-test')
    calls=[]
    def fake(system,payload,schema,**kw):
        calls.append({'system':system,'payload':payload,'contents':kw.get('contents')})
        return schema.model_validate(answers[min(len(calls),len(answers))-1]),{'mode':'LIVE','model':'gemini-test','latency_ms':40}
    monkeypatch.setattr(engine,'structured_generate',fake);return calls
@pytest.fixture(autouse=True)
def local(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER','local');monkeypatch.setenv('AUTH_PROVIDER','synthetic_demo')

def test_rm_copilot_answers_from_the_open_relationship_with_labelled_evidence():
    p=dina();ctx=c.get('/v1/rm/copilot/context?party_id='+p['id'],headers=h()).json()
    assert ctx['scope']=='PARTY' and ctx['scope_label']=='Dina Rahma · assigned to you' and ctx['base_version']==p['version'] and len(ctx['starters'])==3
    r=ask(ctx['starters'][0],party_id=p['id'],base_version=p['version']);assert r.status_code==200,r.text;turn=r.json()
    assert turn['mode']=='SIMULATED' and turn['points'] and {x['id'] for x in turn['refs']}=={i for pt in turn['points'] for i in pt['refs']}
    with SessionLocal() as db:assert db.query(ReviewEvent).filter_by(resource_id=p['id'],action='AI_COPILOT_ANSWERED').count()==1

def test_book_scope_covers_only_the_rms_own_work():
    ctx=c.get('/v1/rm/copilot/context',headers=h()).json()
    assert ctx['scope']=='BOOK' and ctx['starters'][0]=='Who should I contact first today?'
    turn=ask('Who should I contact first today?').json()
    assert all(r['record_type'] in {'signal','followup','prospect','book','policy'} for r in turn['refs'])

def test_staff_assistants_deny_other_roles_and_unassigned_relationships():
    p=dina()
    for user in ['usr-dina','usr-aiadmin','usr-quality']:
        assert c.get('/v1/rm/copilot/context?party_id='+p['id'],headers=h(user)).status_code==403
        assert ask('Who is this?',user,party_id=p['id'],base_version=p['version']).status_code==403
    for user in ['usr-dina','usr-maya']:
        assert c.get('/v1/rm/quality-assistant/context',headers=h(user)).status_code==403
        assert analyst('Show me the traces',user).status_code==403
    with SessionLocal() as db:db.get(Party,p['id']).owner_id='other-rm';db.commit()
    assert ask('Who is this?',party_id=p['id'],base_version=p['version']).status_code==403

def test_a_stale_relationship_or_run_version_is_a_conflict_not_an_answer():
    p=dina()
    assert ask('Why now?',party_id=p['id'],base_version=p['version']+1).status_code==409
    assert ask('Why now?',party_id=p['id']).status_code==422
    run=c.post('/v1/rm/evaluations',headers=h('usr-aiadmin'),json={'request_key':str(uuid.uuid4())}).json()
    assert analyst('What does this run show?',run_id=run['id'],base_version=run['version']+1).status_code==409
    assert analyst('What does this run show?',run_id=run['id'],base_version=run['version']).status_code==200

def test_invented_number_is_rejected_after_one_repair_with_no_fallback(monkeypatch):
    p=dina();calls=live(monkeypatch,{'answer':'Dina can afford IDR 9,999,999 a month.','points':[]})
    r=ask('What can she afford?',party_id=p['id'],base_version=p['version'])
    assert r.status_code==502 and 'unsupported number' in r.json()['detail'] and 'No simulated fallback' in r.json()['detail']
    assert len(calls)==2 and '9,999,999' in calls[1]['payload']['rejected_previous_attempt']
    with SessionLocal() as db:assert db.query(ReviewEvent).filter_by(resource_id=p['id'],action='AI_COPILOT_FAILED').count()==1

def test_provider_failure_returns_an_honest_error(monkeypatch):
    p=dina();monkeypatch.setenv('NEXTRM_AI_PROVIDER','vertex');monkeypatch.delenv('GEMINI_MODEL',raising=False)
    r=ask('Why now?',party_id=p['id'],base_version=p['version'])
    assert r.status_code==503 and 'No simulated fallback' in r.json()['detail']

def test_live_answer_labels_inference_and_gates_drafts_on_contact_permission(monkeypatch):
    from test_ai_rm_assist import setup_followup
    fid,src,pid=setup_followup(contact='RESTRICTED')
    live(monkeypatch,{'answer':'Lead with her own words.','points':[{'text':'She wants to discuss options for 2026.','kind':'EVIDENCE','source_ids':[src]},{'text':'She may want a liquidity check first.','kind':'INFERENCE','source_ids':[]}],'suggestions':['What should I ask first?'],'action':'DRAFT','action_target':'followup:'+fid})
    p=dina();turn=ask('Draft my outreach',party_id=pid,base_version=p['version']).json()
    assert turn['mode']=='LIVE' and [x['evidence'] for x in turn['points']]==['CUSTOMER_SAID','INFERENCE']
    assert turn['action']['kind']=='DRAFT' and turn['action']['available'] is False and 'restricted' in turn['action']['reason']

def test_unknown_record_ids_are_rejected(monkeypatch):
    p=dina();live(monkeypatch,{'answer':'See the other customer.','points':[{'text':'Another customer asked too.','kind':'EVIDENCE','source_ids':['SRC-someone-else']}]})
    r=ask('Anyone similar?',party_id=p['id'],base_version=p['version'])
    assert r.status_code==502 and 'unauthorized or nonexistent record' in r.json()['detail']

def test_metadata_admin_never_receives_conversation_text(monkeypatch):
    customer=c.get('/v1/rm/parties',headers=h('usr-dina')).json()['parties'][0]['id']
    version=c.get('/v1/rm/chat/'+customer,headers=h('usr-dina')).json()['version']
    turn=c.post('/v1/rm/chat/'+customer+'/turns',headers=h('usr-dina'),json={'message':'Where is my money going, zebracode?','base_version':version,'request_key':str(uuid.uuid4())}).json()
    with SessionLocal() as db:db.get(Turn,turn['id']).share=True;db.commit()
    calls=live(monkeypatch,{'answer':'Recent turns are recorded.','points':[]})
    assert analyst('What did customers ask?').status_code==200
    assert 'zebracode' not in json.dumps(calls[0]['payload']) and calls[0]['payload']['content_access'] is False
    assert analyst('What did customers ask?','usr-quality').status_code==200
    assert 'zebracode' in json.dumps(calls[1]['payload']) and calls[1]['payload']['content_access'] is True

def test_a_ratio_must_cite_the_metric_that_defines_it():
    cards={'metric:qa':copilot.card('metric:qa','MEASURED','QA correctness','22 of 24 cases (91.67%). Rubric: reference.'),'run:1':copilot.card('run:1','MEASURED','Evaluation run','Suite v2, 24 cases.',record_type='run',record_id='1')}
    scope={'scope':'QUALITY','cards':cards,'busy':False,'governor':True,'party':None}
    def parsed(ref):return copilot.CopilotModel(answer='QA correctness is 91.67%.',points=[{'text':'22 of 24 cases passed.','kind':'EVIDENCE','source_ids':[ref]}])
    with pytest.raises(ProviderFailure,match='ratio'):copilot.validate(parsed('run:1'),'QUALITY',scope,'How good is it?',[])
    assert copilot.validate(parsed('metric:qa'),'QUALITY',scope,'How good is it?',[])['points'][0]['evidence']=='MEASURED'
