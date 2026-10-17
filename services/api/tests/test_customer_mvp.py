"""Bank chatbot + insights + observed signals; not an in-app RM messenger."""
import json,uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.core.security import CurrentUser
from app.models.relationships import Party,Signal,Source,AppActivity,Turn
from app.services.customer_activity import seed_customer_activity,record_activity
from app.services.money_display import money_text
client=TestClient(app)
def h(user='usr-dina'):return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def key():return str(uuid.uuid4())
def pid():return client.get('/v1/rm/parties',headers=h()).json()['parties'][0]['id']
def send(message,**extra):
    c=client.get('/v1/rm/chat/'+pid(),headers=h()).json()
    return client.post('/v1/rm/chat/'+pid()+'/turns',headers=h(),json={'message':message,'base_version':c['version'],'request_key':key(),**extra})
@pytest.fixture(autouse=True)
def local(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER','local');monkeypatch.setenv('AUTH_PROVIDER','synthetic_demo');monkeypatch.delenv('NEXTRM_CAPTURE_POLICY_JSON',raising=False);monkeypatch.delenv('NEXTRM_RM_CONTACTS_JSON',raising=False)

def test_chat_signal_capture_uses_bank_policy_without_a_per_turn_checkbox():
    r=send('I want a savings account for school expenses');assert r.status_code==200,r.text;assert r.json()['signal_id']
    with SessionLocal() as db:assert json.loads(db.get(Turn,r.json()['id']).output_json)['capture_method']=='INSTITUTION_POLICY'
    assert send('How does a time deposit work?').json()['signal_id'] is None

def test_private_turn_and_capture_disabled_keep_help_without_rm_signal(monkeypatch):
    r=send('Keep this private. I want a deposit.');assert r.json()['signal_id'] is None
    with SessionLocal() as db:
        source_id=json.loads(db.get(Turn,r.json()['id']).output_json)['message_source_id'];assert db.get(Source,source_id).kind=='PRIVATE_CUSTOMER_MESSAGE'
    assert client.get('/v1/rm/sources/'+source_id,headers=h('usr-maya')).status_code==403
    assert client.get('/v1/rm/sources/'+source_id,headers=h()).status_code==200
    monkeypatch.setenv('NEXTRM_CAPTURE_POLICY_JSON',json.dumps({'demo-bank':{'enabled':False,'channels':[],'version':'disabled-v1'}}))
    r=send('I want a savings account.');assert r.status_code==200 and r.json()['answer'] and r.json()['signal_id'] is None

def test_financial_question_has_validated_snapshot_numbers_and_source_refs():
    r=send('Why has my spending increased?');assert r.status_code==200,r.text
    assert 'IDR 1,150,000' in r.json()['answer'] and '1150000.00' not in r.json()['answer'] and '27.78%' in r.json()['answer']
    assert any(s['kind']=='BANK_DATA_SUMMARY' for s in r.json()['sources'])
    assert any(t['name']=='read_permitted_financial_context' for t in r.json()['tools'])
    assert r.json()['signal_id'] is None
    r=send('Help me understand my cash flow');cash=next(i for i in client.get('/v1/rm/chat/'+pid()+'/engagement',headers=h()).json()['insights'] if i['key']=='cash_flow')
    assert money_text(cash['values']['difference'],'IDR') in r.json()['answer'] and 'not a live balance' in r.json()['answer']

def test_observed_product_views_have_exact_count_deduplication_and_no_hot_label():
    for n in range(20):
        body={'request_key':key(),'kind':'PRODUCT_VIEW','product':'DEPOSIT'}
        r=client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(),json=body);assert r.status_code==200,r.text
        assert client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(),json=body).json()==r.json()
    out=client.get('/v1/rm/parties/'+pid()+'/behavior',headers=h('usr-maya')).json()
    assert out['events'][0]['count']==20 and out['events'][0]['window']=='Rolling 7 days'
    assert len(out['signals'])==1 and out['signals'][0]['category']=='RESEARCH' and not out['signals'][0]['confirmed'] and out['signals'][0]['display_label']!='Hot lead'
    with SessionLocal() as db:
        signal=db.get(Signal,out['signals'][0]['id']);assert json.loads(db.get(Source,signal.source_id).content)['count']==20
    assert client.post('/v1/rm/signals/'+out['signals'][0]['id']+'/review',headers=h('usr-maya'),json={'base_version':out['signals'][0]['version'],'decision':'ACCEPTED','confirmed':True}).status_code==422

def test_failure_is_from_synthetic_adapter_not_forged_customer_opening_workflow():
    with SessionLocal() as db:seed_customer_activity(db);db.commit()
    out=client.get('/v1/rm/parties/'+pid()+'/behavior',headers=h('usr-maya')).json()
    assert any(x['kind']=='APPLICATION_FAILED' and x['mode']=='SIMULATED' for x in out['events'])
    assert any(x['category']=='SERVICE_ISSUE' and 'credit decision' in x['need'] for x in out['signals'])
    assert client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(),json={'request_key':key(),'kind':'APPLICATION_FAILED','product':'LOAN'}).status_code==422
    with SessionLocal() as db:
        count=db.query(AppActivity).count();seed_customer_activity(db);db.commit();assert db.query(AppActivity).count()==count
        assert db.get(Party,pid()).relationship=='EXISTING_CUSTOMER'

def test_official_contact_is_tenant_owned_configuration_and_missing_is_honest(monkeypatch):
    path='/v1/rm/chat/'+pid()+'/rm-contact';r=client.get(path,headers=h());assert r.status_code==200
    assert r.json()['name']=='Maya Putri' and r.json()['status']=='NOT_CONFIGURED' and r.json()['email_href'] is None and r.json()['phone_href'] is None
    monkeypatch.setenv('NEXTRM_RM_CONTACTS_JSON',json.dumps({'demo-bank':{'usr-maya':{'email':'maya@bank.example','phone':'+621234567890'}}}))
    r=client.get(path,headers=h()).json();assert r['email_href']=='mailto:maya@bank.example' and r['phone_href']=='tel:+621234567890'
    monkeypatch.setenv('NEXTRM_RM_CONTACTS_JSON',json.dumps({'demo-bank':{'usr-maya':{'email':'x@bank.example?subject=secret'}}}))
    assert client.get(path,headers=h()).status_code==503

def test_behavior_contact_and_activity_do_not_bypass_role_or_subject():
    assert client.get('/v1/rm/parties/'+pid()+'/behavior',headers=h()).status_code==403
    for user in ['usr-maya','usr-aiadmin','usr-quality']:
        assert client.get('/v1/rm/chat/'+pid()+'/rm-contact',headers=h(user)).status_code==403
        assert client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(user),json={'request_key':key(),'kind':'PRODUCT_VIEW','product':'DEPOSIT'}).status_code==403
    p=next(p for p in client.get('/v1/rm/parties',headers=h('usr-maya')).json()['parties'] if p['name']=='Aditya Pratama')
    assert client.get('/v1/rm/chat/'+p['id']+'/rm-contact',headers=h()).status_code==404

def test_financial_signals_are_observed_guidance_not_sales_confirmation():
    with SessionLocal() as db:seed_customer_activity(db);db.commit()
    r=client.get('/v1/rm/chat/'+pid()+'/engagement',headers=h());assert r.status_code==200
    signals=client.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals']
    assert any(x['category']=='GUIDANCE' and 'Spending changed' in x['title'] and not x['confirmed'] for x in signals)

def test_cashflow_help_is_guidance_not_a_confirmed_sales_opportunity():
    r=send('I need help understanding my cash flow');assert r.status_code==200 and r.json()['signal_id']
    s=next(x for x in client.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if x['id']==r.json()['signal_id'])
    assert s['category']=='GUIDANCE' and s['display_label']!='Hot lead'

def test_financial_context_never_displaces_urgent_card_help():
    r=send('My card was stolen. I need help with my balance.');assert r.status_code==200
    assert r.json()['route']=='CARD' and 'verified' in r.json()['answer'] and '12500000' not in r.json()['answer']

def test_contact_restriction_suppresses_product_research_signals_and_failure_help_survives():
    with SessionLocal() as db:p=db.get(Party,pid());p.contact='RESTRICTED';db.commit()
    for _ in range(6):assert client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(),json={'request_key':key(),'kind':'PRODUCT_VIEW','product':'DEPOSIT'}).status_code==200
    assert not client.get('/v1/rm/parties/'+pid()+'/behavior',headers=h('usr-maya')).json()['signals']
    with SessionLocal() as db:seed_customer_activity(db);db.commit()
    out=client.get('/v1/rm/parties/'+pid()+'/behavior',headers=h('usr-maya')).json()
    assert any(s['category']=='SERVICE_ISSUE' for s in out['signals'])

@pytest.mark.parametrize('kind,product',[('PRODUCT_VIEW','NONE'),('RM_CONTACT_VIEW','DEPOSIT')])
def test_invalid_event_product_combination_is_rejected(kind,product):
    assert client.post('/v1/rm/chat/'+pid()+'/activity',headers=h(),json={'request_key':key(),'kind':kind,'product':product}).status_code==422

def test_reported_loan_opening_error_is_service_help_not_credit_rejection():
    r=send('I tried opening a loan in the bank app but it failed. Can you help?');assert r.status_code==200 and r.json()['signal_id']
    assert 'does not establish loan rejection' in r.json()['answer']
    s=next(x for x in client.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if x['id']==r.json()['signal_id'])
    assert s['category']=='SERVICE_ISSUE' and not s['confirmed']

def test_explicit_time_deposit_need_is_distinct_from_repeated_view_observation():
    r=send('I want to open a time deposit for my savings.');assert r.status_code==200 and r.json()['signal_id']
    s=next(x for x in client.get('/v1/rm/signals',headers=h('usr-maya')).json()['signals'] if x['id']==r.json()['signal_id'])
    assert s['evidence']=='CUSTOMER_CONFIRMED' and s['review']=='PROPOSED' and s['display_label']=='Potential opportunity'
