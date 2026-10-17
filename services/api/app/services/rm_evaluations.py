"""Durable bounded reference-case jobs. Actual results; developer fixtures, not a validated model rating."""
import json,time,os,math,statistics
from datetime import timedelta
from pathlib import Path
from sqlalchemy import update,or_,text
from ..models.relationships import EvaluationRun,Turn,Party
from ..models.entities import UserAssignmentModel,utc_now
from .rm import j,uid,stamp,quality_grant,kb_for,source_data
from fastapi import HTTPException
from .menus import destination_data
from .assistant.engine import LOCAL_MODEL,PROMPT_VERSION,respond,provider_info,ProviderFailure,ProviderUnavailable
SUITE_VERSION='relationship-reference-v2'
ROOT=Path(__file__).resolve().parents[4]

def eval_data(run):
    config=json.loads(run.config_json);digest=__import__('hashlib').sha256(j({k:v.get('hash') for k,v in config.get('knowledge',{}).items()}).encode()).hexdigest()[:12]
    return {'id':run.id,'status':run.status,'version':run.version,'suite_version':run.suite_version,'model':config.get('model','UNKNOWN'),'source_digest':digest,'mode':run.mode,'created_at':stamp(run.created_at),'updated_at':stamp(run.updated_at),'results':json.loads(run.results_json),'error':run.error}

def process_evaluation(db):
    from ..models.relationships import QualityGrant
    run=db.query(EvaluationRun).filter(EvaluationRun.status.in_(['QUEUED','RUNNING'])).order_by(EvaluationRun.created_at).first()
    if not run:return False
    now=utc_now();token=uid('LEASE')
    claimed=db.execute(update(EvaluationRun).where(EvaluationRun.id==run.id,or_(EvaluationRun.lease_until.is_(None),EvaluationRun.lease_until<now)).values(lease_token=token,lease_until=now+timedelta(seconds=60),status='RUNNING'))
    if claimed.rowcount!=1:db.rollback();return False
    db.commit();db.refresh(run)
    member=db.query(UserAssignmentModel).filter_by(user_id=run.actor_id,tenant_id=run.tenant_id,active=True).first();grant=db.query(QualityGrant).filter_by(user_id=run.actor_id,tenant_id=run.tenant_id,active=True).first()
    if not member or not grant:run.status='FAILED';run.error='Requester access was revoked.';run.lease_until=None;db.commit();return True
    config=json.loads(run.config_json)
    provider,ready=provider_info();current_model=os.getenv('GEMINI_MODEL','') if provider!='local' else LOCAL_MODEL;expected='SIMULATED' if provider=='local' else 'LIVE'
    if not ready or expected!=run.mode or config.get('provider')!=provider or config.get('model')!=current_model or config.get('prompt_version')!=PROMPT_VERSION:run.status='FAILED';run.error='Provider configuration/mode changed; no fallback was used.';run.lease_until=None;db.commit();return True
    cases=config['cases'];results=json.loads(run.results_json);kb=config['knowledge']
    for case in cases[len(results):len(results)+5]:
        start=time.perf_counter()
        try:
            answer=respond(case['question'],'',kb,{'name':'Synthetic evaluation person','declared_goal':'','mode':'SYNTHETIC','governance_context':__import__('app.services.governance',fromlist=['resolve']).resolve(config.get('governance_definition',__import__('app.services.governance',fromlist=['DEFAULT']).DEFAULT),case['question'],release_id=config.get('governance_release'),version=config.get('governance_version',0))})
            qa=answer.route==case['route'] and case['contains'].casefold() in answer.text.casefold()
            tools=(answer.route==case['route'] and {x['name'] for x in answer.tools}==({'read_approved_knowledge','read_permitted_customer_context'} if case['tools']==2 else {'read_approved_knowledge'}) and all(x['status']=='COMPLETED' for x in answer.tools))
            supported=sum(1 for claim in answer.claims if any(src['id']==claim['source_id'] and claim['text']==src['content'] for src in kb.values()))
            results.append({'case_id':case['id'],'family':case['family'],'question':case['question'],'expected_route':case['route'],'actual_route':answer.route,'qa_pass':qa,'tool_pass':tools,'supported_claims':supported,'assessable_claims':len(answer.claims),'latency_ms':max(1,int((time.perf_counter()-start)*1000)),'status':'COMPLETED','answer':answer.text,'reason':'Developer reference rubric: route + required material phrase; tools and exact source excerpts checked. Unadjudicated.'})
        except (ProviderUnavailable,ProviderFailure) as e:
            results.append({'case_id':case['id'],'family':case['family'],'question':case['question'],'expected_route':case['route'],'actual_route':'UNAVAILABLE','qa_pass':False,'tool_pass':False,'supported_claims':0,'assessable_claims':0,'latency_ms':int((time.perf_counter()-start)*1000),'status':'FAILED','answer':'','reason':str(e)})
        run.results_json=j(results);run.updated_at=utc_now();db.commit()
    run.status='COMPLETED' if len(results)==len(cases) else 'RUNNING';run.version+=1;run.lease_until=None;run.lease_token=None;db.commit();return True

def percentile(values,fraction):
    if not values:return None
    values=sorted(values)
    if fraction==.5:return round(statistics.median(values))
    return values[max(0,min(len(values)-1,math.ceil(len(values)*fraction)-1))]

def quality_summary(db,user):
    grant=quality_grant(db,user);provider,ready=provider_info();mode='SIMULATED' if provider=='local' else 'LIVE';now=stamp(utc_now())
    turns=db.query(Turn).filter_by(tenant_id=user.tenant_id).order_by(Turn.created_at.desc()).limit(100).all()
    if user.role=='RM':turns=[t for t in turns if t.actor_id==user.user_id]
    traces=[];scopes=set(json.loads(grant.party_scope_json));knowledge=kb_for(db,user.tenant_id) if grant.content else {}
    for t in turns[:30]:
        content=bool(grant.content and t.share and t.party_id in scopes);party=db.query(Party).filter_by(id=t.party_id,tenant_id=user.tenant_id).first() if content else None;out=json.loads(t.output_json)
        traces.append({'id':t.id,'party_id':t.party_id,'name':party.name if party and content else 'Scoped customer turn','route':t.route,'status':t.status,'mode':t.mode,'model':t.model,'latency_ms':t.latency_ms,'at':stamp(t.created_at),'message':t.message if content else None,'answer':t.answer if content else None,'tools':json.loads(t.tools_json),'sources':[x for x in knowledge.values() if x['id'] in out.get('source_ids',[])] if content else [],'error_code':t.error_code,'content_access':content,'context_source_id':out.get('context_source_id'),'context_source_version':out.get('context_source_version'),'context_source_hash':out.get('context_source_hash'),'prompt_version':out.get('prompt_version','UNKNOWN'),'governance':out.get('governance'),'thinking_level':out.get('thinking_level')})
    runs=db.query(EvaluationRun).filter_by(tenant_id=user.tenant_id).order_by(EvaluationRun.created_at.desc()).limit(6).all()
    current_model=LOCAL_MODEL if provider=='local' else os.getenv('GEMINI_MODEL','')
    latest=next((x for x in runs if x.status=='COMPLETED' and x.mode==mode and json.loads(x.config_json).get('model')==current_model and json.loads(x.config_json).get('prompt_version')==PROMPT_VERSION),None);metrics=[]
    if latest:
        results=json.loads(latest.results_json);assessable=sum(x['assessable_claims'] for x in results);supported=sum(x['supported_claims'] for x in results)
        metrics=[{'label':'QA correctness','numerator':sum(x['qa_pass'] for x in results),'denominator':len(results),'unit':'cases','method':'Pinned developer reference rubric; unadjudicated unless explicitly reviewed.'},{'label':'Tool selection','numerator':sum(x['tool_pass'] for x in results),'denominator':len(results),'unit':'cases','method':'Expected scoped context/knowledge tools and route/no-tool behavior.'},{'label':'Unsupported-claim rate','numerator':assessable-supported,'denominator':assessable,'unit':'assessable source excerpts','method':'Exact approved-source excerpt support only; not universal factual correctness or a guaranteed hallucination detector.'}]
    latencies=[x.latency_ms for x in turns if x.status=='COMPLETED' and x.mode==mode]
    worker_recent=False
    try:
        marker=Path(os.environ.get('NEXTRM_WORKER_HEALTH_FILE',str(ROOT/'runtime/local-worker-health.json')))
        if marker.exists():
            health=json.loads(marker.read_text())
            if isinstance(health,dict):
                age=utc_now().timestamp()-float(health.get('at',0))
                worker_recent=0<=age<10 and health.get('database_fingerprint')==__import__('hashlib').sha256(str(db.get_bind().engine.url).encode()).hexdigest()[:12]
    except (ValueError,TypeError,OSError):pass
    db.execute(text('SELECT 1'))
    try:
        configured=any(x['status']=='READY' for x in destination_data(user.tenant_id)['destinations'])
        menu_status='CONFIGURED_NOT_VERIFIED' if configured else 'NOT_CONFIGURED'
        menu_detail='Institution-owned menu links configured; separate banking workflows remain outside NextRM. POI is synthetic.' if configured else 'Bank menu links are not configured; product/service actions remain outside NextRM. POI is synthetic.'
    except HTTPException:
        menu_status='UNAVAILABLE';menu_detail='Institution menu configuration is invalid; no fallback link is invented.'
    health=[{'name':'API and database','status':'HEALTHY','detail':'This authorized request and SELECT 1 succeeded.','checked_at':now},{'name':'Conversation provider','status':'LOCAL_SIMULATION' if provider=='local' and ready else 'CONFIGURED_NOT_VERIFIED' if ready else 'UNAVAILABLE','detail':'Fast governed local engine; no Google model call.' if provider=='local' else 'Google configuration present; verify with a genuine call.' if ready else 'Missing provider configuration. No fallback.','checked_at':now},{'name':'Evaluation worker','status':'HEALTHY' if worker_recent else 'NOT_OBSERVED','detail':'Recent matching local worker heartbeat.' if worker_recent else 'Start the documented durable local worker; queued runs stay queued.','checked_at':now},{'name':'Product menus / POI','status':menu_status,'detail':menu_detail,'checked_at':now}]
    return {'provider':provider,'provider_ready':ready,'model_mode':mode,'turn_count':len(turns),'error_count':sum(t.status=='FAILED' for t in turns),'p50_ms':percentile(latencies,.5),'p95_ms':percentile(latencies,.95),'metrics':metrics,'traces':traces,'runs':[eval_data(x) for x in runs],'health':health,'content_access':grant.content,'method_note':'Latest 100 tenant-scoped turns (RM metadata limited to own turns). Median is the sample median; p95 uses nearest rank. Quality uses the latest completed matching-mode/model developer suite. Local simulation is not a measured Gemini score or pilot outcome.'}
