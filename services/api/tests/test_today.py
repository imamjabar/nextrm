import json,uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Turn,Signal,Journey,AppActivity
from app.services.customer_activity import seed_customer_activity
from test_relationship_mvp import chat,dina
c=TestClient(app)
def h(user='usr-maya'):return {'X-User-Id':user,'X-Tenant-Id':'demo-bank'}
def today():r=c.get('/v1/rm/today',headers=h());assert r.status_code==200,r.text;return r.json()
def own_party(user):return c.get('/v1/rm/parties',headers=h(user)).json()['parties']
@pytest.fixture(autouse=True)
def local(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER','local');monkeypatch.setenv('AUTH_PROVIDER','synthetic_demo')

def test_today_counts_tally_with_the_lists_they_summarise():
    d=today();signals=[x for x in c.get('/v1/rm/signals',headers=h()).json()['signals'] if x['workflow'] not in {'COMPLETED','DISMISSED'}]
    tasks=[x for x in c.get('/v1/rm/follow-ups',headers=h()).json()['journeys'] if x['status'] not in {'DONE','CANCELLED'}]
    assert d['counts']['needs_open']==len(signals) and d['counts']['needs_to_review']==sum(x['review']=='PROPOSED' for x in signals)
    assert d['counts']['followups_open']==len(tasks) and d['counts']['customers']==len(d['customers']) and len(d['queue'])<=20

def test_captured_chat_reaches_the_rm_and_private_chat_never_does():
    before=today()['counts']['conversations_today']
    r,_=chat('Why did my spending go up this month?');assert r.status_code==200,r.text
    d=today();assert any(x['kind']=='CHAT' and x['name']=='Dina Rahma' and x['text']=='Why did my spending go up this month?' for x in d['activity'])
    assert d['counts']['conversations_today']==before+1
    r,_=chat('Keep this private: my salary is late');assert r.status_code==200,r.text
    d=today();assert not any('salary is late' in x['text'] for x in d['activity']) and d['counts']['conversations_today']==before+1
    snap=c.get('/v1/rm/parties/'+dina()['id']+'/snapshot',headers=h()).json();assert not any('salary is late' in x['text'] for x in snap['conversations'])

def test_rm_snapshot_shows_the_customer_home_figures_and_is_rm_only():
    pid=dina()['id'];mine={x['key']:x['values'] for x in c.get('/v1/rm/chat/'+pid+'/engagement',headers=h('usr-dina')).json()['insights']}
    r=c.get('/v1/rm/parties/'+pid+'/snapshot',headers=h());assert r.status_code==200 and r.json()['available']
    rm={x['key']:x['values'] for x in r.json()['insights']}
    for key in ['cash_flow','spending_breakdown','portfolio','net_worth']:assert rm[key]==mine[key]
    for user in ['usr-dina','usr-aiadmin']:assert c.get('/v1/rm/parties/'+pid+'/snapshot',headers=h(user)).status_code==403

def test_rm_followup_progress_reaches_the_customer_without_internal_notes():
    r,_=chat('Talk to my RM about my portfolio');assert r.status_code==200 and r.json()['signal_id'],r.text
    sid=r.json()['signal_id'];s=next(x for x in c.get('/v1/rm/signals',headers=h()).json()['signals'] if x['id']==sid)
    s=c.post('/v1/rm/signals/'+sid+'/review',headers=h(),json={'base_version':s['version'],'decision':'ACCEPTED','confirmed':True}).json()
    j=c.post('/v1/rm/signals/'+sid+'/follow-up',headers=h(),json={'base_version':s['version'],'request_key':str(uuid.uuid4())});assert j.status_code==200,j.text;j=j.json()
    u=c.post('/v1/rm/follow-ups/'+j['id'],headers=h(),json={'base_version':j['version'],'request_key':str(uuid.uuid4()),'action':'START','note':'Private validation-only note','due_at':'2030-01-15T10:00:00+07:00'});assert u.status_code==200,u.text
    r=c.get('/v1/rm/chat/'+dina()['id']+'/requests',headers=h('usr-dina'));assert r.status_code==200
    item=next(x for x in r.json()['requests'] if x['id']==sid);assert item['status']=='RM_PREPARING' and item['due_at']
    assert 'Private validation-only' not in r.text

def test_seeded_story_is_linked_repeat_safe_and_reaches_both_sides():
    with SessionLocal() as db:
        seed_customer_activity(db);db.commit();counts=[db.query(m).count() for m in (Turn,Signal,Journey,AppActivity)]
        seed_customer_activity(db);db.commit();assert [db.query(m).count() for m in (Turn,Signal,Journey,AppActivity)]==counts
        seeded=db.query(Signal).filter(Signal.semantic_key.startswith('SEED-')).all();assert len(seeded)==3
        for s in seeded:assert json.loads(db.get(Turn,s.turn_id).output_json)['signal_id']==s.id
    for user,name in [('usr-aditya','Aditya Pratama'),('usr-nabila','Nabila Aulia')]:
        me=c.get('/v1/auth/me',headers=h(user));assert me.status_code==200 and me.json()['user']['role']=='CUSTOMER'
        parties=own_party(user);assert [x['name'] for x in parties]==[name]
    nabila=own_party('usr-nabila')[0]['id']
    requests=c.get('/v1/rm/chat/'+nabila+'/requests',headers=h('usr-nabila')).json()['requests']
    assert any('debit card' in x['message'] and x['status']=='RM_PREPARING' for x in requests)
    assert any(x['kind']=='CHAT' and x['name']=='Aditya Pratama' and 'term deposit' in x['text'] for x in today()['activity'])

def test_today_queue_is_care_first_then_newest():
    d=today();q=d['queue'];groups=('PROBLEM','READY','ASKED','SPOTTED')
    assert len(q)>0
    indexes=[groups.index(item['signal']['group']) for item in q]
    assert indexes==sorted(indexes)
    for g in groups:
        dates=[item['signal']['created_at'] for item in q if item['signal']['group']==g]
        assert dates==sorted(dates,reverse=True)
    for item in q:
        s=item['signal']
        if s['category']=='SERVICE_ISSUE':assert s['group']=='PROBLEM'
        if s['origin']=='CHAT':assert item['quote']

def test_empty_new_chat_is_not_listed():
    pid=dina()['id'];key=str(uuid.uuid4())
    r=c.post('/v1/rm/chat/'+pid+'/sessions',headers=h('usr-dina'),json={'request_key':key})
    assert r.status_code==200,r.text;sid=r.json()['id']
    sessions=c.get('/v1/rm/chat/'+pid+'/sessions',headers=h('usr-dina')).json()['sessions']
    assert not any(x['id']==sid for x in sessions)
    sess=c.get('/v1/rm/chat/'+pid+'/sessions/'+sid,headers=h('usr-dina')).json()
    t=c.post('/v1/rm/chat/'+pid+'/turns',headers=h('usr-dina'),json={'base_version':sess['version'],'session_id':sid,'request_key':str(uuid.uuid4()),'message':'How does a time deposit work?'})
    assert t.status_code==200,t.text
    sessions=c.get('/v1/rm/chat/'+pid+'/sessions',headers=h('usr-dina')).json()['sessions']
    row=next((x for x in sessions if x['id']==sid),None)
    assert row is not None and row['turn_count']==1
