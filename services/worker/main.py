"""Local durable evaluation worker. API acknowledgement follows job commit; work runs here."""
import os,sys,time,json,hashlib,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/api'))
from app.core.database import SessionLocal,engine
from app.services.rm_evaluations import process_evaluation
running=True

def stop(*_):
    global running
    running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
print('NextRM local durable worker started.',flush=True)
while running:
    try:
        with SessionLocal() as db:worked=process_evaluation(db)
        marker=Path(os.environ.get('NEXTRM_WORKER_HEALTH_FILE',str(ROOT/'runtime/local-worker-health.json')))
        marker.parent.mkdir(parents=True,exist_ok=True);tmp=marker.with_suffix('.'+str(os.getpid())+'.tmp')
        tmp.write_text(json.dumps({'at':time.time(),'database_fingerprint':hashlib.sha256(str(engine.url).encode()).hexdigest()[:12]}));tmp.replace(marker)
        if not worked:time.sleep(.5)
    except Exception as exc:
        print('Worker unit failed; durable run retained for recovery: '+type(exc).__name__,flush=True);time.sleep(1)
print('NextRM worker stopped.',flush=True)
