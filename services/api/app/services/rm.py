import json,hashlib,uuid,os
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import update
from ..models.relationships import Party,ContactLink,Source,Signal,Journey,ReviewEvent,QualityGrant,Turn
from ..models.entities import UserAssignmentModel,utc_now
from .assistant.engine import provider_info,ROUTE_KB

j=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)
def uid(prefix):return prefix+'-'+uuid.uuid4().hex
def stamp(value):return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()
def hash_payload(value):return hashlib.sha256(j(value).encode()).hexdigest()
def require_rm(user):
    if user.role!='RM':raise HTTPException(403,'Assigned relationship-manager access required.')
def party_for(db,user,pid,customer=False):
    if customer and user.role!='CUSTOMER':
        raise HTTPException(403,'Sign in with the customer account to use the phone, chatbot or customer preferences. RM and admin accounts have separate workspaces.')
    p=db.query(Party).filter_by(id=pid,tenant_id=user.tenant_id).first()
    if not p:raise HTTPException(404,'Relationship not found in your permitted scope.')
    if user.role=='CUSTOMER':
        if user.entity_id!=p.id:raise HTTPException(404,'Relationship not found in your permitted scope.')
    elif user.role=='RM':
        from .coverage import can_read
        if not can_read(db,user,p):raise HTTPException(403,'This relationship is not assigned to you.')
    else:raise HTTPException(403,'This role cannot access this relationship surface.')
    return p

def scoped_signal(db,user,id):
    require_rm(user);s=db.query(Signal).filter_by(id=id,tenant_id=user.tenant_id).first()
    if not s:raise HTTPException(404,'Signal not found.')
    party_for(db,user,s.party_id)
    if s.owner_id!=user.user_id:raise HTTPException(403,'This signal is not assigned to you.')
    if not db.query(Source).filter_by(id=s.source_id,tenant_id=user.tenant_id,party_id=s.party_id).first():raise HTTPException(409,'Signal source binding requires repair; no protected content is returned.')
    return s

def scoped_journey(db,user,id):
    r=db.query(Journey).filter_by(id=id,tenant_id=user.tenant_id).first()
    if not r:raise HTTPException(404,'Journey not found.')
    party_for(db,user,r.party_id)
    if not db.query(Source).filter_by(id=r.source_id,tenant_id=user.tenant_id,party_id=r.party_id).first():raise HTTPException(409,'Journey source binding requires repair.')
    return r

def cas(db,model,row,base):
    changed=db.execute(update(model).where(model.id==row.id,model.tenant_id==row.tenant_id,model.version==base).values(version=model.version+1))
    if changed.rowcount!=1:raise HTTPException(409,'This record changed. Reload and compare the current version before reviewing.')
    db.refresh(row)

def quality_grant(db,user):
    g=db.query(QualityGrant).filter_by(tenant_id=user.tenant_id,user_id=user.user_id,active=True).first()
    if not g or user.role not in {'QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'}:raise HTTPException(403,'Use an authorized AI administration account with an explicit institution quality grant.')
    return g

def source_data(s):
    return {'id':s.id,'title':s.title,'content':s.content,'kind':s.kind,'mode':s.mode,'version':s.version,'hash':s.content_hash,'event_at':stamp(s.event_at),'ingested_at':stamp(s.ingested_at)}

def party_data(db,p):
    ctx=json.loads(p.context_json);owner=db.query(UserAssignmentModel).filter_by(user_id=p.owner_id,tenant_id=p.tenant_id).first();contacts=[]
    for link in db.query(ContactLink).filter_by(tenant_id=p.tenant_id,organization_id=p.id).all():
        person=db.query(Party).filter_by(id=link.person_id,tenant_id=p.tenant_id).first()
        if person:
            # Contact projection excludes personal products, goals and internal notes.
            contacts.append({'id':link.id,'person_id':person.id,'name':person.name,'role':link.role,'email':json.loads(link.details_json).get('contact_email','Not supplied in the company source'),'source_ref':link.source_ref,'authority':'Not established by contact role'})
    from .coverage import coverage_for
    coverage=coverage_for(db,p)
    owner_name=owner.name if owner else 'Assigned RM'
    if coverage and coverage.mode!='DEDICATED':owner_name='Relationship service team'
    return {'id':p.id,'name':p.name,'kind':p.kind,'segment':p.segment,'owner_id':p.owner_id,'owner_name':owner_name,'relationship':p.relationship,'identity':p.identity,'contact':p.contact,'locality':p.locality,'customer_ref':p.customer_ref,'version':p.version,'products':ctx.get('products',[]),'declared_goal':ctx.get('declared_goal',''),'occupation':ctx.get('occupation',''),'contact_channel':ctx.get('contact_channel','IN_APP'),'contact_purpose':ctx.get('contact_purpose','Needs discussion'),'email':ctx.get('email',''),'mode':'SYNTHETIC','contacts':contacts}

CHAT_SOURCES={'CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE'}
NEED_GROUPS=('PROBLEM','READY','ASKED','SPOTTED')
def need_origin(s,source):return 'APP' if s.semantic_key.startswith('APP-') else 'INSIGHT' if s.semantic_key.startswith('FIN-') else 'CHAT' if source and source.kind in CHAT_SOURCES else 'EVENT'
def need_group(s,origin,hot):return 'PROBLEM' if s.category=='SERVICE_ISSUE' else 'READY' if hot else 'ASKED' if origin=='CHAT' else 'SPOTTED'
def need_order(row):return (NEED_GROUPS.index(row['group']),-datetime.fromisoformat(row['created_at']).timestamp(),row['id'])

def signal_data(db,s):
    p=db.query(Party).filter_by(id=s.party_id,tenant_id=s.tenant_id).one();source=db.query(Source).filter_by(id=s.source_id,tenant_id=s.tenant_id,party_id=s.party_id).first()
    fresh=source and (utc_now()-source.event_at.replace(tzinfo=timezone.utc)).days<=30
    hot=s.category=='OPPORTUNITY' and s.confirmed and s.review in {'ACCEPTED','EDITED'} and s.workflow not in {'DISMISSED','COMPLETED'} and p.contact=='ALLOWED' and p.identity=='CONFIRMED' and fresh
    origin=need_origin(s,source)
    return {'id':s.id,'party_id':p.id,'name':p.name,'category':s.category,'urgency':s.urgency,'evidence':s.evidence,'workflow':s.workflow,'review':s.review,'title':s.title,'need':s.need,'rationale':s.rationale+(' Hot-lead rule REL-1: explicit sourced interest, accepted review, fresh evidence, confirmed identity and current permitted follow-up.' if hot else '')+ ' Priority rule PRI-1: urgent/time-sensitive help, service need, evidence and freshness before routine commercial work.','uncertainty':('Interpretation reviewed. Destination/product outcome remains unconfirmed; no approval or execution is implied.' if s.review in {'ACCEPTED','EDITED'} else s.uncertainty),'confirmed':s.confirmed,'version':s.version,'source_id':s.source_id,'turn_id':s.turn_id,'created_at':stamp(s.created_at),'display_label':'Hot lead' if hot else 'Potential opportunity' if s.category=='OPPORTUNITY' else s.category.replace('_',' ').title(),'contact':p.contact,'origin':origin,'group':need_group(s,origin,hot)}

def journey_data(db,x):
    from ..models.relationships import FollowupDetail
    detail=db.query(FollowupDetail).filter_by(id=x.id,tenant_id=x.tenant_id).first()
    p=db.query(Party).filter_by(id=x.party_id,tenant_id=x.tenant_id).one()
    return {'id':x.id,'party_id':p.id,'name':p.name,'kind':x.kind,'need':x.need,'status':x.status,'stage':x.stage,'version':x.version,'operation_ref':x.operation_ref,'draft':x.draft,'source_id':x.source_id,'signal_id':x.signal_id,'prospect_id':x.prospect_id,'history':json.loads(x.history_json),'due_at':next((h.get('due_at') for h in reversed(json.loads(x.history_json)) if h.get('due_at')),None),'completion_rule':'RM records completion of the follow-up work. This is not product opening, approval, activation or service resolution.' if x.kind=='RM_FOLLOWUP' else 'Account opening AND first relevant activation acknowledged for this party.' if x.kind=='ONBOARDING_ACTIVATION' else 'Recorded RM-conversation outcome with reviewed need; no product activation implied.' if x.kind=='RM_CONVERSATION' else 'Service-resolution receipt plus configured customer confirmation.','mode':'HUMAN_RECORDED' if x.kind=='RM_FOLLOWUP' else 'SIMULATED','snoozed_until':stamp(detail.snoozed_until) if detail and detail.snoozed_until else None,'outcome':detail.outcome if detail else None}

def review_event(db,user,resource,action,reason,before,after):
    db.add(ReviewEvent(id=uid('REVIEW'),tenant_id=user.tenant_id,resource_id=resource,actor_id=user.user_id,action=action,reason=reason,before_json=j(before),after_json=j(after)))

def kb_for(db,tenant):
    rows=db.query(Source).filter_by(tenant_id=tenant,kind='APPROVED_KNOWLEDGE').all()
    kb={s.id.split('KB-')[-1]:source_data(s) for s in rows}
    if not set(ROUTE_KB.values()).issubset(kb):raise HTTPException(503,'Approved institution knowledge is not seeded. Run the explicit local seed command.')
    return kb

def turn_data(db,t):
    out=json.loads(t.output_json);sources=[]
    for id in out.get('source_ids',[]):
        source=db.query(Source).filter_by(id=id,tenant_id=t.tenant_id).first()
        if source and source.kind!='APPROVED_KNOWLEDGE' and (source.party_id!=t.party_id or source.kind not in {'BANK_DATA_SUMMARY','AUTHORIZED_FINANCIAL_SUMMARY'}):source=None
        if source:sources.append(source_data(source))
    return {'id':t.id,'message':t.message,'answer':t.answer,'status':t.status,'route':t.route,'mode':t.mode,'model':t.model,'created_at':stamp(t.created_at),'latency_ms':t.latency_ms,'sources':sources,'tools':json.loads(t.tools_json),'signal_id':out.get('signal_id'),'error_code':t.error_code,'governance':out.get('governance'),'sharing_status':out.get('sharing_status','SHARED' if out.get('signal_id') else 'NOT_RECORDED'),'suggestions':out.get('suggestions',[]),'thinking_level':out.get('thinking_level')}


def priority_key(signal):
    closed=signal.workflow in {'COMPLETED','DISMISSED'}
    urgency={'URGENT':0,'TIME_SENSITIVE':1,'ROUTINE':2}.get(signal.urgency,3)
    service=0 if signal.category=='SERVICE_ISSUE' else 1
    evidence=0 if signal.evidence=='CUSTOMER_CONFIRMED' else 1
    return (closed,urgency,service,evidence,-signal.created_at.replace(tzinfo=timezone.utc).timestamp(),signal.id)

def prospect_priority(prospect,party,source):
    """ACQ-1 is an ordering of permitted work, not propensity or private wealth."""
    if party.relationship=='EXISTING_CUSTOMER' or prospect.disposition=='EXISTING_CUSTOMER':
        return (5,'EXISTING_RELATIONSHIP','Existing relationship in available CRM; duplicate acquisition suppressed.','Open existing relationship')
    if party.identity!='CONFIRMED':
        return (4,'IDENTITY_REVIEW','Identity is unresolved; no automatic merge or commercial follow-up.','Resolve identity through an authorized source')
    if party.contact!='ALLOWED':
        return (4,'CONTACT_RESTRICTED','Current contact permission does not allow commercial follow-up.','Respect the contact restriction')
    if prospect.disposition:
        return (3,'ON_HOLD','Recorded disposition: '+prospect.disposition.replace('_',' ').lower()+'.','Review the recorded disposition')
    age=utc_now()-source.event_at.replace(tzinfo=timezone.utc)
    if age.total_seconds() < -300 or age.days>30:
        return (3,'SOURCE_REVIEW','Source is outside the 30-day freshness window. Reconfirm context and permission.','Refresh the permitted source before follow-up')
    if prospect.state=='FOLLOWUP_PLANNED':
        return (2,'FOLLOWUP_PLANNED','A sourced RM follow-up is already prepared.','Continue the existing RM follow-up')
    if prospect.need_reviewed:
        return (0,'READY_FOR_DISCUSSION','Reviewed need, confirmed identity, current permitted contact and fresh source.','Prepare RM follow-up')
    if source.kind=='SYNTHETIC_OPT_IN' and 'referral' not in source.title.casefold():
        return (1,'REVIEW_FIRST','Supplied opt-in enquiry with identity, contact and freshness checks passed. Confirm the stated need.','Review the sourced need')
    return (2,'REVIEW','Supplied referral or source record; no customer-confirmed need inferred.','Confirm the goal and permitted purpose')


def customer_journey_data(db,x):
    result=journey_data(db,x)
    source=db.query(Source).filter_by(id=x.source_id,tenant_id=x.tenant_id,party_id=x.party_id).first()
    result['need']=source.content if source and source.kind in {'CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE'} else 'Your shared journey progress'
    result['draft']='Internal RM drafts are not released to the customer.'
    result['signal_id']=None;result['prospect_id']=None
    result['history']=[{k:v for k,v in h.items() if k in {'event','status','at','reference','mode'}} for h in result['history']]
    return result

def record_ai_audit_event(db,user,action,resource_type,resource_id,mode,model,prompt_version,latency_ms,source_ids):
    meta={'resource_type':resource_type,'mode':mode,'model':model,'prompt_version':prompt_version,'latency_ms':latency_ms,'source_ids':sorted(source_ids)}
    review_event(db,user,resource_id,action,'Gemini generation metadata. Generated text and customer content are not stored.',{},meta)
