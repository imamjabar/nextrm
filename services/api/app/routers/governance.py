import json
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.relationships import GovernanceRelease,ReviewEvent,RMCapacity,CustomerCoverage,Party,Signal,Journey,Prospect,Source
from ..models.entities import UserAssignmentModel,utc_now
from ..schemas.rm import *
from ..services.rm import cas,j,uid,hash_payload,stamp,review_event,require_rm,signal_data,contact_preferences_for_signals
from ..services.governance import require_governor,draft_for,released,validate_definition,test_definition,resolve,BOUNDARIES
from ..services.coverage import capacity_for,dedicated_count,active_count,POOL_OWNER
router=APIRouter(prefix='/v1/rm',tags=['governance-and-coverage'])

def governance_data(db,user):
    row=draft_for(db,user.tenant_id);definition=json.loads(row.definition_json);_,id,version=released(db,user.tenant_id)
    releases=db.query(GovernanceRelease).filter_by(tenant_id=user.tenant_id).order_by(GovernanceRelease.version.desc()).limit(20).all()
    return {'version':row.version,'definition':definition,'tested':row.tested_digest==hash_payload(definition),'tests':json.loads(row.test_json),'release_id':id,'release_version':version,'history':[{'id':r.id,'version':r.version,'digest':r.digest,'actor':r.actor_id,'at':stamp(r.created_at)} for r in releases],'boundaries':BOUNDARIES}

@router.get('/governance',response_model=RMGovernance)
def governance(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);result=governance_data(db,user);db.commit();return result

@router.post('/governance',response_model=RMGovernance)
def save(req:RMGovernanceUpdate,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);definition=validate_definition(req.definition.model_dump())
    if len(j(definition).encode())>12000:raise HTTPException(422,'Keep the bounded policy below 12 KB; reduce duplicate keywords/examples.')
    row=draft_for(db,user.tenant_id);old={'digest':hash_payload(json.loads(row.definition_json)),'version':row.version};cas(db,type(row),row,req.base_version)
    row.definition_json=j(definition);row.tested_digest=None;row.test_json='[]';row.updated_at=utc_now()
    review_event(db,user,row.id,'GOVERNANCE_DRAFT',req.reason,old,{'digest':hash_payload(definition),'version':row.version});db.commit();return governance_data(db,user)

@router.post('/governance/test',response_model=RMGovernance)
def test(req:RMGovernanceAction,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);row=draft_for(db,user.tenant_id)
    if row.version!=req.base_version:raise HTTPException(409,'Policy draft changed; reload before testing.')
    cas(db,type(row),row,req.base_version)
    definition=validate_definition(json.loads(row.definition_json));tests=test_definition(definition);row.test_json=j(tests)
    row.tested_digest=hash_payload(definition) if tests and all(t['passed'] for t in tests) else None
    review_event(db,user,row.id,'GOVERNANCE_TEST',req.reason,{}, {'digest':hash_payload(definition),'passed':sum(t['passed'] for t in tests),'cases':len(tests)});db.commit();return governance_data(db,user)

@router.post('/governance/publish',response_model=RMGovernance)
def publish(req:RMGovernanceAction,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);payload=hash_payload(req.model_dump());old=db.query(GovernanceRelease).filter_by(tenant_id=user.tenant_id,request_key=req.request_key).first()
    if old:
        receipt=db.query(ReviewEvent).filter_by(tenant_id=user.tenant_id,resource_id=old.id,action='GOVERNANCE_PUBLISH').first()
        if not receipt or json.loads(receipt.after_json).get('payload_hash')!=payload:raise HTTPException(409,'Publish key conflicts with its original request.')
        return governance_data(db,user)
    row=draft_for(db,user.tenant_id);definition=validate_definition(json.loads(row.definition_json));digest=hash_payload(definition)
    if row.tested_digest!=digest or not json.loads(row.test_json) or not all(t['passed'] for t in json.loads(row.test_json)):raise HTTPException(409,'Test the unchanged draft successfully before publishing.')
    cas(db,type(row),row,req.base_version);_,previous,version=released(db,user.tenant_id)
    release=GovernanceRelease(id=uid('POLICY'),tenant_id=user.tenant_id,version=version+1,definition_json=j(definition),digest=digest,actor_id=user.user_id,request_key=req.request_key);db.add(release);db.flush()
    review_event(db,user,release.id,'GOVERNANCE_PUBLISH',req.reason,{'release':previous}, {'release':release.id,'version':release.version,'digest':digest,'payload_hash':payload});db.commit();return governance_data(db,user)

@router.post('/governance/preview',response_model=RMPolicyPreview)
def preview(req:RMPolicyTest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user)
    if req.use_draft:definition=json.loads(draft_for(db,user.tenant_id).definition_json);return resolve(definition,req.question)
    definition,id,version=released(db,user.tenant_id);return resolve(definition,req.question,release_id=id,version=version)

@router.get('/assignments',response_model=RMAssignments)
def assignments(cursor:str='',db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);members=db.query(UserAssignmentModel).filter_by(tenant_id=user.tenant_id,role='RM',active=True).all();rms=[]
    for m in members:
        c=capacity_for(db,user.tenant_id,m.user_id);rms.append({'id':m.user_id,'name':m.name,'version':c.version,'dedicated_limit':c.dedicated_limit,'case_limit':c.case_limit,'pool_enabled':c.pool_enabled,'dedicated_customers':dedicated_count(db,user.tenant_id,m.user_id),'active_cases':active_count(db,user.tenant_id,m.user_id)})
    query=db.query(Party).filter_by(tenant_id=user.tenant_id,relationship='EXISTING_CUSTOMER')
    if cursor:query=query.filter(Party.id>cursor)
    parties=query.order_by(Party.id).limit(101).all();customers=[]
    for p in parties[:100]:
        coverage=db.query(CustomerCoverage).filter_by(tenant_id=user.tenant_id,party_id=p.id).first()
        customers.append({'id':p.id,'name':p.name,'kind':p.kind,'version':p.version,'mode':coverage.mode if coverage else 'DEDICATED','rm_id':coverage.rm_id if coverage else p.owner_id,'tier':coverage.tier if coverage else 'STANDARD','pool_id':coverage.pool_id if coverage else 'shared-service'})
    db.commit();return {'rms':rms,'customers':customers,'next_cursor':parties[99].id if len(parties)>100 else None,'pool_cases':db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=POOL_OWNER).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).count(),'method':'Institution-assigned service tier, dedicated book capacity and shared case queues. No automatic HNW classification from balances or unlimited RM allocation.'}

@router.post('/assignments/rms/{id}',response_model=RMAssignments)
def set_capacity(id:str,req:RMCapacityUpdate,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user)
    if not db.query(UserAssignmentModel).filter_by(tenant_id=user.tenant_id,user_id=id,role='RM',active=True).first():raise HTTPException(404,'Active institution RM not found.')
    c=capacity_for(db,user.tenant_id,id,lock=True)
    if req.dedicated_limit<dedicated_count(db,user.tenant_id,id) or req.case_limit<active_count(db,user.tenant_id,id):raise HTTPException(409,'Capacity cannot be below current allocation; rebalance or finish work first.')
    old={'dedicated_limit':c.dedicated_limit,'case_limit':c.case_limit,'pool_enabled':c.pool_enabled};cas(db,RMCapacity,c,req.base_version)
    c.dedicated_limit=req.dedicated_limit;c.case_limit=req.case_limit;c.pool_enabled=req.pool_enabled
    review_event(db,user,c.id,'RM_CAPACITY',req.reason,old,{'dedicated_limit':c.dedicated_limit,'case_limit':c.case_limit,'pool_enabled':c.pool_enabled});db.commit();return assignments('',db,user)

@router.post('/assignments/customers/{pid}',response_model=RMAssignments)
def set_coverage(pid:str,req:RMCoverageUpdate,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_governor(user);p=db.query(Party).filter_by(id=pid,tenant_id=user.tenant_id,relationship='EXISTING_CUSTOMER').first()
    if not p:raise HTTPException(404,'Institution customer not found.')
    receipt_id='COVERAGE-'+hash_payload({'tenant':user.tenant_id,'key':req.request_key})[:48];receipt=db.get(ReviewEvent,receipt_id);payload=hash_payload({'party':pid,**req.model_dump()})
    if receipt:
        if json.loads(receipt.after_json).get('payload_hash')!=payload:raise HTTPException(409,'Assignment key conflicts.')
        return assignments('',db,user)
    if db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=pid,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED'])).first():raise HTTPException(409,'Finish or cancel current RM work before moving coverage; its ownership/history is retained.')
    if req.mode=='DEDICATED':
        member=db.query(UserAssignmentModel).filter_by(tenant_id=user.tenant_id,user_id=req.rm_id,role='RM',active=True).first()
        if not member:raise HTTPException(422,'Choose an active RM in this institution.')
        capacity=capacity_for(db,user.tenant_id,req.rm_id,lock=True)
        current=db.query(CustomerCoverage).filter_by(tenant_id=user.tenant_id,party_id=pid).first()
        already=(current.mode=='DEDICATED' and current.rm_id==req.rm_id) if current else p.owner_id==req.rm_id
        if not already and dedicated_count(db,user.tenant_id,req.rm_id)>=capacity.dedicated_limit:raise HTTPException(409,'Dedicated RM capacity is full; choose shared coverage or another RM.')
    elif req.rm_id:raise HTTPException(422,'Shared/digital coverage does not have a dedicated RM.')
    old={'owner':p.owner_id};cas(db,Party,p,req.base_version)
    c=db.query(CustomerCoverage).filter_by(tenant_id=user.tenant_id,party_id=pid).first()
    if not c:c=CustomerCoverage(id=uid('COVERAGE'),tenant_id=user.tenant_id,party_id=pid,mode=req.mode);db.add(c)
    else:c.version+=1
    c.mode=req.mode;c.rm_id=req.rm_id if req.mode=='DEDICATED' else None;c.tier=req.tier
    if req.mode=='DEDICATED':p.owner_id=req.rm_id
    owner=req.rm_id if req.mode=='DEDICATED' else POOL_OWNER
    for s in db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=pid).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])):
        source=db.query(Source).filter_by(id=s.source_id,tenant_id=user.tenant_id,party_id=pid).first()
        human=bool(source and (source.kind=='CUSTOMER_RM_REQUEST' or (source.kind=='CUSTOMER_MESSAGE' and __import__('app.services.assistant.engine',fromlist=['human_help_requested']).human_help_requested(source.content))))
        s.owner_id=('DIGITAL:'+user.tenant_id if req.mode=='DIGITAL' and s.category!='SERVICE_ISSUE' and not human else owner);s.version+=1
    # Existing-customer duplicates remain held; do not silently reassign historical acquisition records.
    for prospect in db.query(Prospect).filter_by(tenant_id=user.tenant_id,party_id=pid):prospect.owner_id=p.owner_id
    db.add(ReviewEvent(id=receipt_id,tenant_id=user.tenant_id,resource_id=p.id,actor_id=user.user_id,action='CUSTOMER_COVERAGE',reason=req.reason,before_json=j(old),after_json=j({'mode':req.mode,'rm_id':c.rm_id,'tier':c.tier,'payload_hash':payload})));db.commit();return assignments('',db,user)

@router.get('/pool',response_model=RMPool)
def pool(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);capacity=capacity_for(db,user.tenant_id,user.user_id)
    if not capacity.pool_enabled:raise HTTPException(403,'You are not enabled for the institution shared pool.')
    rows=db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=POOL_OWNER).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).order_by(Signal.created_at.desc()).limit(100).all()
    prefs=contact_preferences_for_signals(db,user.tenant_id,[s.id for s in rows])
    return {'signals':[signal_data(db,s,pref=prefs.get(s.id)) for s in rows],'capacity':capacity.case_limit,'active_cases':active_count(db,user.tenant_id,user.user_id),'method':'Only scoped event/need summaries are visible before a capacity-checked claim. Customer detail access is granted for the active claimed case.'}

@router.post('/pool/{id}/claim',response_model=RMPool)
def claim(id:str,req:RMPoolClaim,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);capacity=capacity_for(db,user.tenant_id,user.user_id,lock=True)
    if not capacity.pool_enabled:raise HTTPException(403,'Shared pool access is disabled.')
    receipt_id='CLAIM-'+hash_payload({'tenant':user.tenant_id,'actor':user.user_id,'key':req.request_key})[:48];payload=hash_payload({'signal':id,**req.model_dump()});receipt=db.get(ReviewEvent,receipt_id)
    if receipt:
        if json.loads(receipt.after_json).get('payload_hash')!=payload:raise HTTPException(409,'Claim key conflicts.')
        return pool(db,user)
    s=db.query(Signal).filter_by(id=id,tenant_id=user.tenant_id,owner_id=POOL_OWNER).first()
    if not s or s.workflow in {'COMPLETED','DISMISSED'}:raise HTTPException(409,'The pool case is no longer available.')
    source=db.query(Source).filter_by(id=s.source_id,tenant_id=user.tenant_id,party_id=s.party_id).first();party=db.query(Party).filter_by(id=s.party_id,tenant_id=user.tenant_id).first()
    if not source or not party:raise HTTPException(409,'Case source/subject binding requires repair.')
    if s.category!='SERVICE_ISSUE' and (party.contact!='ALLOWED' or party.identity!='CONFIRMED'):raise HTTPException(403,'Commercial case is restricted; requested service help remains available.')
    if s.category!='SERVICE_ISSUE' and not __import__('app.services.enrichment',fromlist=['fresh']).fresh(source):raise HTTPException(409,'Refresh stale case evidence before claiming commercial work.')
    if active_count(db,user.tenant_id,user.user_id)>=capacity.case_limit:raise HTTPException(409,'Your active case capacity is full.')
    cas(db,Signal,s,req.base_version);s.owner_id=user.user_id
    db.add(ReviewEvent(id=receipt_id,tenant_id=user.tenant_id,resource_id=s.id,actor_id=user.user_id,action='POOL_CLAIM',reason='Capacity-checked RM claimed the current need.',before_json=j({'owner':POOL_OWNER}),after_json=j({'owner':user.user_id,'payload_hash':payload})));db.commit();return pool(db,user)
