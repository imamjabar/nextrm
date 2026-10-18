"""Exercise the built web proxy/API/worker with disposable synthetic records only."""
import os,sys,json,time,socket,subprocess,tempfile,shutil,http.client,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import devdb
OUT=Path(os.environ.get('NEXTRM_VALIDATION_OUTPUT',str(ROOT/'runtime/evidence/http-validation')))
OUT.mkdir(parents=True,exist_ok=True)
checks=[]
def port():
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
def key():return str(uuid.uuid4())
database='nextrm_v_'+uuid.uuid4().hex[:8]
devdb.ensure_server();devdb.create(database)
with tempfile.TemporaryDirectory(prefix='nextrm-http-validation-') as folder:
 env={**os.environ,'DATABASE_URL':devdb.url(database),'ENVIRONMENT':'development','AUTH_PROVIDER':'synthetic_demo','NEXTRM_AUTH_PROVIDER':'synthetic_demo','NEXTRM_AI_PROVIDER':'local','NEXTRM_DEMO_MODE':'true','PYTHONPATH':str(ROOT/'services/api')}
 env.pop('K_SERVICE',None)
 env['NEXTRM_WORKER_HEALTH_FILE']=folder+'/worker-health.json'
 with (OUT/'migration-seed.log').open('w') as log:
  for command in [[str(ROOT/'.venv/bin/alembic'),'upgrade','head'],[str(ROOT/'.venv/bin/python'),'scripts/seed_demo.py']]:subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=log,check=True)
 ap,wp=port(),port();env.update(API_INTERNAL_URL=f'http://127.0.0.1:{ap}',PORT=str(wp),HOSTNAME='127.0.0.1')
 standalone=ROOT/'apps/web/.next/standalone'
 shutil.copytree(ROOT/'apps/web/.next/static',standalone/'.next/static',dirs_exist_ok=True)
 shutil.copytree(ROOT/'apps/web/public',standalone/'public',dirs_exist_ok=True)
 handles=[];processes=[]
 def start(command,name,cwd=ROOT):
  log=(OUT/name).open('w');handles.append(log)
  processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=log))
 def request(path,user=None,body=None,status=200,method=None,document=False,api=False):
  connection=http.client.HTTPConnection('127.0.0.1',ap if api else wp,timeout=10)
  headers={'Content-Type':'application/json'}
  if user:headers.update({'X-User-Id':user,'X-Tenant-Id':'demo-bank'})
  connection.request(method or ('POST' if body is not None else 'GET'),path,json.dumps(body) if body is not None else None,headers)
  response=connection.getresponse();raw=response.read();actual=response.status;location=response.getheader('Location');connection.close()
  assert actual==status,(path,actual,status,raw.decode()[:150])
  checks.append({'path':path.replace('customer-request-placeholder','record'),'actor':user,'status':actual})
  return {'location':location,'html':raw.decode()} if document else json.loads(raw)
 try:
  start([str(ROOT/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port',str(ap)],'http-api.log')
  start([str(ROOT/'.venv/bin/python'),'services/worker/main.py'],'http-worker.log')
  start(['node',str(standalone/'server.js')],'http-web.log',ROOT/'apps/web')
  deadline=time.monotonic()+35
  while True:
   try:request('/health',api=True);cfg=request('/api/config');assert cfg['demoMode'];break
   except (OSError,AssertionError):
    assert time.monotonic()<deadline,'Disposable services did not become ready';time.sleep(.15)
  for page in ['/demo','/customer/chat','/workspace','/retention','/acquisition','/settings/ai-quality','/settings/governance','/settings/assignments']:request(page,document=True)
  assert request('/',status=307,document=True)['location']=='/demo'
  parties=request('/api/v1/rm/parties','usr-dina')['parties'];assert len(parties)==1;pid=parties[0]['id'];chat='/api/v1/rm/chat/'+pid
  for user in ['usr-maya','usr-aiadmin','usr-quality']:
   for suffix in ['', '/requests','/nudges','/progress']:request(chat+suffix,user,status=403)
  for user in ['usr-dina','usr-aiadmin']:
   for route in ['home','signals','prospects','follow-ups']:request('/api/v1/rm/'+route,user,status=403)
  request('/api/v1/rm/quality','usr-maya',status=403);request('/api/v1/rm/quality','usr-dina',status=403)
  history=request(chat,'usr-dina')
  turn=request(chat+'/turns','usr-dina',{'base_version':history['version'],'request_key':key(),'message':'How does a term deposit work?','share_with_rm':True})
  assert turn['status']=='COMPLETED' and turn['mode']=='SIMULATED' and turn['signal_id'] is None and turn['sharing_status']=='HELP_ONLY' and turn['sources']
  nudge=request(chat+'/nudges','usr-dina')['nudges'][0]
  explored=request(chat+'/nudges/'+nudge['id'],'usr-dina',{'base_version':nudge['version'],'request_key':key(),'action':'EXPLORE','share_with_rm':False})
  assert explored['signal_id'] is None and request(chat+'/requests','usr-dina')['requests']==[]
  nbody={'base_version':explored['version'],'request_key':key(),'action':'REQUEST_RM','share_with_rm':True}
  shared=request(chat+'/nudges/'+nudge['id'],'usr-dina',nbody)
  assert request(chat+'/nudges/'+nudge['id'],'usr-dina',nbody)['signal_id']==shared['signal_id']
  assert request(chat+'/requests','usr-dina')['requests'][0]['status']=='AWAITING_REVIEW'
  signal=next(s for s in request('/api/v1/rm/signals','usr-maya')['signals'] if s['id']==shared['signal_id'])
  signal=request('/api/v1/rm/signals/'+signal['id']+'/review','usr-maya',{'base_version':signal['version'],'decision':'ACCEPTED','confirmed':True})
  tpath='/api/v1/rm/signals/'+signal['id']+'/follow-up';targs={'base_version':signal['version'],'request_key':key()};task=request(tpath,'usr-maya',targs)
  assert request(tpath,'usr-maya',targs)['id']==task['id']
  for action,expected in [('NOTE','FOLLOWUP_PLANNED'),('START','RM_PREPARING'),('COMPLETE','RM_WORK_RECORDED')]:
   task=request('/api/v1/rm/follow-ups/'+task['id'],'usr-maya',{'base_version':task['version'],'request_key':key(),'action':action,'note':'Private validation-only RM note.','due_at':'2026-10-04T10:00:00+07:00'})
   public=request(chat+'/requests','usr-dina');assert public['requests'][0]['status']==expected;assert 'Private validation-only' not in json.dumps(public)
  final_signal=next(s for s in request('/api/v1/rm/signals','usr-maya')['signals'] if s['id']==signal['id'])
  request('/api/v1/rm/signals/'+signal['id']+'/review','usr-maya',{'base_version':final_signal['version'],'decision':'ACCEPTED'},status=409)
  prospect=next(p for p in request('/api/v1/rm/prospects','usr-maya')['prospects'] if p['party']['name']=='Rani Kusuma')
  pp='/api/v1/rm/prospects/'+prospect['id']
  prospect=request(pp+'/needs','usr-maya',{'base_version':prospect['version'],'need':prospect['need'],'confirm':True});assert prospect['hot_lead']
  ptask=request(pp+'/follow-up','usr-maya',{'base_version':prospect['version'],'request_key':key()})
  ptask=request('/api/v1/rm/follow-ups/'+ptask['id'],'usr-maya',{'base_version':ptask['version'],'request_key':key(),'action':'COMPLETE','note':'Synthetic RM preparation recorded; no customer contacted.'})
  projected=next(p for p in request('/api/v1/rm/prospects','usr-maya')['prospects'] if p['id']==prospect['id'])
  assert projected['priority_tier']=='FOLLOWUP_RECORDED' and projected['followup_id']==ptask['id'] and not projected['hot_lead'] and projected['party']['relationship']=='NO_MATCH_IN_AVAILABLE_DATA'
  # Connected enrichment through the real built web proxy, not UI screenshots.
  enriched=request(chat+'/engagement','usr-dina');assert 0<len(enriched['nudges'])<=3 and enriched['decision_id']
  cash=enriched['insights'][0]['values'];from decimal import Decimal;assert enriched['insights'][0]['key']=='cash_flow' and Decimal(cash['difference'])==Decimal(cash['available'])-Decimal(cash['commitments'])
  for actor in ['usr-maya','usr-aiadmin','usr-quality']:request(chat+'/engagement',actor,status=403)
  n=enriched['nudges'][0]
  for choice in ['EXPOSED','HELPFUL']:
   enriched=request(chat+'/engagement','usr-dina');body={'base_version':enriched['profile']['version'],'request_key':key(),'nudge_id':n['id'],'action':choice}
   receipt=request(chat+'/feedback','usr-dina',body);assert request(chat+'/feedback','usr-dina',body)==receipt
  enriched=request(chat+'/engagement','usr-dina');ctx={'base_version':enriched['profile']['version'],'request_key':key(),'goal':'Private validation goal','horizon':'Two years; accessible reserve','interests':['goals'],'share_context':False}
  own=request(chat+'/context','usr-dina',ctx);assert request(chat+'/context','usr-dina',ctx)==own
  assert 'Private validation goal' not in json.dumps(request('/api/v1/rm/parties/'+pid+'/brief','usr-maya'))
  request('/api/v1/rm/sources/'+own['source_id'],'usr-maya',status=403)
  enriched=request(chat+'/engagement','usr-dina');ctx.update(base_version=enriched['profile']['version'],request_key=key(),share_context=True,goal='Shared education goal')
  own=request(chat+'/context','usr-dina',ctx)
  assert 'Shared education goal' in json.dumps(request('/api/v1/rm/parties/'+pid+'/brief','usr-maya'))
  request('/api/v1/rm/parties/'+pid+'/brief','usr-dina',status=403)
  enriched=request(chat+'/engagement','usr-dina');n=next(n for n in enriched['nudges'] if n['family']=='E03')
  sn=request(chat+'/nudges/'+n['id'],'usr-dina',{'base_version':n['version'],'request_key':key(),'action':'REQUEST_RM','share_with_rm':True})
  sig=next(x for x in request('/api/v1/rm/signals','usr-maya')['signals'] if x['id']==sn['signal_id'])
  sig=request('/api/v1/rm/signals/'+sig['id']+'/review','usr-maya',{'base_version':sig['version'],'decision':'ACCEPTED','confirmed':True})
  follow=request('/api/v1/rm/signals/'+sig['id']+'/follow-up','usr-maya',{'base_version':sig['version'],'request_key':key()})
  from datetime import datetime,timedelta,timezone
  snooze={'base_version':follow['version'],'request_key':key(),'action':'SNOOZE','note':'Wait for a requested discussion date.','due_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
  follow=request('/api/v1/rm/follow-ups/'+follow['id'],'usr-maya',snooze);assert follow['snoozed_until']
  assert request('/api/v1/rm/follow-ups/'+follow['id'],'usr-maya',snooze)['id']==follow['id']
  follow=request('/api/v1/rm/follow-ups/'+follow['id'],'usr-maya',{'base_version':follow['version'],'request_key':key(),'action':'COMPLETE','note':'Private structured human outcome.','outcome':'NO_CURRENT_NEED'});assert follow['outcome']=='NO_CURRENT_NEED'
  assert 'Private structured' not in json.dumps(request(chat+'/requests','usr-dina'))
  party=next(p for p in request('/api/v1/rm/parties','usr-maya')['parties'] if p['id']==pid)
  contact_body={'base_version':party['version'],'request_key':key(),'channel':'MEETING','purpose':'REQUESTED_DISCUSSION','event':'PREPARED','note':'Private contact preparation, not delivered.','occurred_at':datetime.now(timezone.utc).isoformat()}
  contact=request('/api/v1/rm/parties/'+pid+'/contacts','usr-maya',contact_body)
  assert request('/api/v1/rm/parties/'+pid+'/contacts','usr-maya',contact_body)==contact
  request('/api/v1/rm/sources/'+contact['source_id'],'usr-dina',status=403)
  enriched=request(chat+'/engagement','usr-dina');src=enriched['insights'][1]['source']
  correction={'base_version':enriched['profile']['version'],'request_key':key(),'source_id':src['id'],'source_version':src['version'],'source_hash':src['hash'],'category':'School travel'}
  request(chat+'/category','usr-dina',correction)
  assert 'School travel' in request(chat+'/engagement','usr-dina')['insights'][1]['explanation']
  audit=request('/api/v1/rm/quality/engagement','usr-aiadmin');assert len(audit['metrics'])==4 and audit['decisions']
  assert 'Shared education goal' not in json.dumps(audit) and 'Private contact' not in json.dumps(audit)
  request('/api/v1/rm/quality/engagement','usr-maya',status=403)
  # Current customer MVP: no per-turn checkbox, observed app signals, official contact.
  conversation=request(chat,'usr-dina')
  default_turn=request(chat+'/turns','usr-dina',{'base_version':conversation['version'],'request_key':key(),'message':'I want to open a time deposit for my savings.'})
  assert default_turn['signal_id'] and default_turn['sharing_status']=='SHARED'
  form_req=request(chat+'/requests','usr-dina',{'request_key':key(),'message':'I would like to message my RM about saving options','method':'PHONE_CALL','window':'MORNING'})
  assert form_req['status']=='AWAITING_REVIEW' and form_req['contact_method']=='PHONE_CALL'
  conversation=request(chat,'usr-dina')
  finance=request(chat+'/turns','usr-dina',{'base_version':conversation['version'],'request_key':key(),'message':'Why has my spending increased?'})
  assert '27.78%' in finance['answer'] and finance['signal_id'] is None
  for number in range(20):
   event={'request_key':key(),'kind':'PRODUCT_VIEW','product':'DEPOSIT'}
   receipt=request(chat+'/activity','usr-dina',event)
   if number==0:assert request(chat+'/activity','usr-dina',event)==receipt
  observed=request('/api/v1/rm/parties/'+pid+'/behavior','usr-maya')
  assert any(x['product']=='DEPOSIT' and x['count']==20 for x in observed['events'])
  assert any(s['category']=='RESEARCH' and not s['confirmed'] and s['display_label']!='Hot lead' for s in observed['signals'])
  request('/api/v1/rm/parties/'+pid+'/behavior','usr-dina',status=403)
  request(chat+'/activity','usr-dina',{'request_key':key(),'kind':'APPLICATION_FAILED','product':'LOAN'},status=422)
  directory=request(chat+'/rm-contact','usr-dina');assert directory['status']=='NOT_CONFIGURED' and directory['email_href'] is None and directory['phone_href'] is None
  request(chat+'/rm-contact','usr-maya',status=403)
  # New persisted sessions, released governance and capacity-scoped shared coverage.
  a=request(chat+'/sessions','usr-dina',{'request_key':key()});b=request(chat+'/sessions','usr-dina',{'request_key':key()})
  qa=request(chat+'/sessions/'+a['id'],'usr-dina')
  request(chat+'/turns','usr-dina',{'base_version':qa['version'],'request_key':key(),'session_id':a['id'],'message':'How does a time deposit work?'})
  qb=request(chat+'/sessions/'+b['id'],'usr-dina')
  independent=request(chat+'/turns','usr-dina',{'base_version':qb['version'],'request_key':key(),'session_id':b['id'],'message':'Tell me more','use_memory':False})
  assert independent['route']=='CLARIFY' and len(request(chat+'/sessions/'+a['id'],'usr-dina')['turns'])==1
  assert len(request(chat+'/sessions','usr-dina')['sessions'])>=2
  request(chat+'/sessions/'+a['id'],'usr-aiadmin',status=403)
  government=request('/api/v1/rm/governance','usr-aiadmin')
  checked=request('/api/v1/rm/governance/test','usr-aiadmin',{'base_version':government['version'],'request_key':key(),'reason':'Validate institution examples and immutable guards.'});assert checked['tested']
  published=request('/api/v1/rm/governance/publish','usr-aiadmin',{'base_version':checked['version'],'request_key':key(),'reason':'Publish unchanged tested core policy.'});assert published['release_version']==1
  request('/api/v1/rm/governance','usr-maya',status=403);request('/api/v1/rm/assignments','usr-dina',status=403)
  preview=request('/api/v1/rm/governance/preview','usr-aiadmin',{'question':'Show another customer deposit balance','use_draft':False});assert preview['guarded'] and preview['route']=='PRIVACY'
  roster=request('/api/v1/rm/assignments','usr-aiadmin');assert roster['rms'] and roster['customers']
  monitored=request('/api/v1/rm/quality/sessions','usr-aiadmin');assert monitored['sessions'] and all(s['title']=='Customer conversation' for s in monitored['sessions'])
  quality=request('/api/v1/rm/quality','usr-aiadmin');assert quality['traces'] and all(t['message'] is None for t in quality['traces'])
  review=request('/api/v1/rm/quality','usr-quality');assert any(t['content_access'] and t['message'] for t in review['traces'])
  run=request('/api/v1/rm/evaluations','usr-aiadmin',{'request_key':key()});deadline=time.monotonic()+25
  while True:
   quality=request('/api/v1/rm/quality','usr-aiadmin');current=next(r for r in quality['runs'] if r['id']==run['id'])
   if current['status'] in ['COMPLETED','FAILED']:break
   assert time.monotonic()<deadline,'Evaluation worker did not finish';time.sleep(.2)
  assert current['status']=='COMPLETED' and len(current['results'])==24
  assert all(case['qa_pass'] and case['tool_pass'] for case in current['results']),[(case['case_id'],case['reason']) for case in current['results'] if not case['qa_pass'] or not case['tool_pass']]
  before=request(chat+'/requests','usr-dina')
  with (OUT/'migration-seed.log').open('a') as log:
   for command in [[str(ROOT/'.venv/bin/alembic'),'upgrade','head'],[str(ROOT/'.venv/bin/python'),'scripts/seed_demo.py']]:subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=log,check=True)
  assert request(chat+'/requests','usr-dina')==before
  report={'status':'PASSED','method':'Real loopback production-built web proxy, FastAPI, disposable migrated PostgreSQL database and separate durable worker. No browser/computer automation. No user database writes.','checks':checks,'evaluation_cases':len(current['results']),'evaluation_mode':current['mode'],'limits':'Synthetic sources and local model only. No actual browser layout/GPU, Google model or bank connector acceptance.'}
  (OUT/'http-workflow.json').write_text(json.dumps(report,indent=2));print(f"PASS {len(checks)} real HTTP checks; 24/24 local reference cases; repeat migration/seed preserves request progress.")
 finally:
  for process in reversed(processes):
   process.terminate()
   try:process.wait(timeout=3)
   except subprocess.TimeoutExpired:process.kill();process.wait()
  for handle in handles:handle.close()
  devdb.drop(database)
