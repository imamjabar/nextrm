"""Measured in-process API workload: ten isolated synthetic sessions, 100 short local turns.
Never measures a Google model or production impact; uses its own disposable database.
"""
import os,sys,json,time,statistics,math,argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'runtime/evidence/performance.json')
args=parser.parse_args()
sys.path.insert(0,str(ROOT/'services/api'))
sys.path.insert(0,str(ROOT/'scripts'))
import devdb
database='nextrm_v_bench_'+str(os.getpid())
devdb.ensure_server();devdb.drop(database);devdb.create(database)
os.environ.update(DATABASE_URL=devdb.url(database),ENVIRONMENT='test',AUTH_PROVIDER='synthetic_demo',NEXTRM_AI_PROVIDER='local')
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base,engine,SessionLocal
from app.core.seeder import seed_demo_database
from app.core.security import DEMO_USERS,CurrentUser
from app.models.entities import UserAssignmentModel
from app.models.relationships import Party
from app.services.assistant.engine import LOCAL_MODEL
Base.metadata.create_all(engine)
with SessionLocal() as db:
    seed_demo_database(db)
    for i in range(10):
        uid='benchmark-user-'+str(i);pid='benchmark-person-'+str(i)
        DEMO_USERS[uid]=CurrentUser(user_id=uid,name='Synthetic benchmark customer',email=uid+'@example.invalid',role='CUSTOMER',tenant_id='demo-bank',institution_type='BANK')
        db.add(UserAssignmentModel(id='ua-'+uid,user_id=uid,name='Synthetic benchmark customer',email=uid+'@example.invalid',role='CUSTOMER',tenant_id='demo-bank',entity_id=pid,active=True))
        db.add(Party(id=pid,tenant_id='demo-bank',kind='PERSON',name='Synthetic benchmark customer',segment='RETAIL',owner_id='usr-maya',relationship='EXISTING_CUSTOMER',identity='CONFIRMED',contact='ALLOWED',locality='Synthetic locality',context_json='{"products":[],"mode":"SYNTHETIC"}'))
    db.commit()

def session(i):
    timings=[];failures=[]
    with TestClient(app) as client:
        h={'X-User-Id':'benchmark-user-'+str(i),'X-Tenant-Id':'demo-bank'};path='/v1/rm/chat/benchmark-person-'+str(i)
        first=client.get(path,headers=h);assert first.status_code==200;version=first.json()['version']
        for n in range(10):
            begin=time.perf_counter();r=client.post(path+'/turns',headers=h,json={'message':'What is a savings account?','base_version':version,'request_key':f'benchmark-{i}-{n}-request','share_with_rm':False});elapsed=(time.perf_counter()-begin)*1000
            if r.status_code==200 and r.json()['status']=='COMPLETED':timings.append(elapsed);version+=1
            else:failures.append({'session':i,'turn':n,'http_status':r.status_code,'status':r.json().get('status','REJECTED')})
    return timings,failures
start=time.perf_counter()
with ThreadPoolExecutor(max_workers=10) as pool:results=list(pool.map(session,range(10)))
timings=[t for r,_ in results for t in r];failures=[f for _,r in results for f in r];ordered=sorted(timings)
report={'workload':'100 short turns / 10 synthetic customer sessions / disposable PostgreSQL / in-process FastAPI TestClient','mode':'SIMULATED','model':LOCAL_MODEL,'attempted':100,'completed':len(timings),'failures':failures,'p50_ms':round(statistics.median(timings),2) if timings else None,'p95_ms':round(ordered[math.ceil(len(ordered)*.95)-1],2) if timings else None,'wall_seconds':round(time.perf_counter()-start,2),'limits':'Not a real TCP/browser or Google model benchmark. Repeated families are not independent quality evidence; no production or ROI claim.'}
out=args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
engine.dispose();devdb.drop(database)
if failures:raise SystemExit('Benchmark included failures; inspect and repair before claiming the declared workload passed.')
