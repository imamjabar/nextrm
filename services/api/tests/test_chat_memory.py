import json,uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import ChatSession,Turn
c=TestClient(app)
def h(user='usr-dina'):return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def key():return str(uuid.uuid4())
def pid():return c.get('/v1/rm/parties',headers=h()).json()['parties'][0]['id']
def session():
 r=c.post('/v1/rm/chat/'+pid()+'/sessions',headers=h(),json={'request_key':key()});assert r.status_code==200,r.text;return r.json()
def send(s,message,**extra):
 q=c.get('/v1/rm/chat/'+pid()+'/sessions/'+s['id'],headers=h()).json()
 r=c.post('/v1/rm/chat/'+pid()+'/turns',headers=h(),json={'base_version':q['version'],'request_key':key(),'session_id':s['id'],'message':message,**extra});assert r.status_code==200,r.text;return r.json()
def memory(exclude,user='usr-dina'):return c.get(f'/v1/rm/chat/{pid()}/memory?exclude={exclude}',headers=h(user))
def recorded(turn_id):
 with SessionLocal() as db:return json.loads(db.get(Turn,turn_id).output_json)['memory']
@pytest.fixture(autouse=True)
def local(monkeypatch):
 monkeypatch.setenv('NEXTRM_AI_PROVIDER','local');monkeypatch.setenv('AUTH_PROVIDER','synthetic_demo');monkeypatch.delenv('NEXTRM_CAPTURE_POLICY_JSON',raising=False)

def test_new_chat_carries_the_customers_earlier_topics_but_not_its_own_turns():
 a=session();send(a,'Why did my transport spending go up?');send(a,'What about Gojek?')
 b=session();remembered=memory(b['id']).json()
 assert remembered['topics'][:2]==['transport','Gojek'] and [x['message'] for x in remembered['items']]==['What about Gojek?','Why did my transport spending go up?']
 assert memory(a['id']).json()=={'topics':[],'items':[]}
 turn=send(b,'How can I spend less this month?')
 assert turn['answer'].startswith('Picking up from your earlier chat about transport and Gojek.')
 assert recorded(turn['id'])=={'used':True,'turn_count':2,'topics':['transport','Gojek']}
 assert 'How can I spend less' not in json.dumps(memory(b['id']).json()),'the current chat is never echoed back as memory'

def test_a_topicless_follow_up_in_a_new_chat_continues_the_earlier_topic():
 send(session(),'How does a time deposit work?')
 assert send(session(),'Tell me more')['route']=='DEPOSIT'
 assert send(session(),'Tell me more',use_memory=False)['route']=='CLARIFY'

def test_customer_can_start_fresh_without_earlier_chats():
 a=session();send(a,'What about Gojek?')
 turn=send(session(),'How can I spend less this month?',use_memory=False)
 assert 'earlier chat' not in turn['answer'] and recorded(turn['id'])['used'] is False and recorded(turn['id'])['turn_count']==0

def test_memory_skips_archived_chats_and_stays_in_the_customers_own_account():
 a=session();send(a,'What about Gojek?')
 with SessionLocal() as db:db.get(ChatSession,a['id']).archived=True;db.commit()
 assert memory(session()['id']).json()['items']==[]
 for user in ['usr-maya','usr-aiadmin','usr-quality']:assert memory('none',user).status_code==403
