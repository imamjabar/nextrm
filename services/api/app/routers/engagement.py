"""RM preparation/follow-up and pulse, without banking execution or reconciliation."""
import json,hashlib,time,os
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.relationships import Journey,Signal,Prospect,Party,Source,Nudge,ReviewEvent
from ..models.entities import utc_now
from ..schemas.rm import RMStartJourney,RMJourney,RMJourneys,RMFollowupUpdate,RMDestinations,RMPulse,RMNudge,RMNudges,RMNudgeAction,RMAIDraftRequest,RMAIDraft,RMSource
from ..services.rm import require_rm,party_for,scoped_signal,scoped_journey,journey_data,customer_journey_data,signal_data,source_data,priority_key,prospect_priority,uid,j,stamp,cas,review_event,hash_payload,record_ai_audit_event
from ..services.assistant.engine import generate_ai_draft,provider_info,ProviderUnavailable,ProviderFailure,PROMPT_DRAFT_VERSION
from ..services.menus import destination_data
router=APIRouter(prefix='/v1/rm',tags=['engagement'])

def task_data(db,row,user):
    return customer_journey_data(db,row) if user.role=='CUSTOMER' else journey_data(db,row)

def existing_task(db,user,payload,key,signal=None,prospect=None):
    old=db.query(Journey).filter_by(tenant_id=user.tenant_id,request_key=key).first()
    if old:
        party_for(db,user,old.party_id)
        if old.kind!='RM_FOLLOWUP' or old.payload_hash!=payload:raise HTTPException(409,'Follow-up request key conflicts with an existing record.')
        return old
    query=db.query(Journey).filter_by(tenant_id=user.tenant_id,kind='RM_FOLLOWUP',actor_id=user.user_id)
    return query.filter_by(signal_id=signal).first() if signal else query.filter_by(prospect_id=prospect).first()

@router.post('/signals/{id}/follow-up',response_model=RMJourney)
def signal_followup(id:str,req:RMStartJourney,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    signal=scoped_signal(db,user,id);party=party_for(db,user,signal.party_id)
    payload=hash_payload({'signal':id,**req.model_dump()});old=existing_task(db,user,payload,req.request_key,signal=id)
    if old:return journey_data(db,old)
    if signal.review not in {'ACCEPTED','EDITED'} or signal.workflow in {'DISMISSED','COMPLETED'}:raise HTTPException(409,'Review the current need before preparing an RM follow-up.')
    if signal.category!='SERVICE_ISSUE' and party.contact!='ALLOWED':raise HTTPException(403,'Commercial follow-up is restricted; service assistance remains available.')
    cas(db,Signal,signal,req.base_version);signal.workflow='IN_PROGRESS'
    task=Journey(id=uid('FOLLOWUP'),tenant_id=user.tenant_id,party_id=party.id,actor_id=user.user_id,source_id=signal.source_id,signal_id=signal.id,kind='RM_FOLLOWUP',request_key=req.request_key,payload_hash=payload,need=signal.need,status='PLANNED',operation_ref=uid('RM-TASK'),draft='Draft only — not sent. '+party.name+', I would like to follow up on your request: '+signal.need+' We can clarify the need and point you to the bank’s appropriate product or service menu.')
    db.add(task);db.flush();review_event(db,user,task.id,'FOLLOWUP_PREPARED','RM preparation only; no destination action.',{}, {'status':'PLANNED','source_id':task.source_id});db.commit();return journey_data(db,task)

@router.post('/prospects/{id}/follow-up',response_model=RMJourney)
def prospect_followup(id:str,req:RMStartJourney,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from .rm import prospect_for
    prospect,party=prospect_for(db,user,id)
    source=db.query(Source).filter_by(id=prospect.source_id,tenant_id=user.tenant_id,party_id=party.id).first()
    if not source:raise HTTPException(409,'Prospect source binding requires repair.')
    payload=hash_payload({'prospect':id,**req.model_dump()});old=existing_task(db,user,payload,req.request_key,prospect=id)
    if old:return journey_data(db,old)
    if party.identity!='CONFIRMED' or party.contact!='ALLOWED':raise HTTPException(403,'Identity/contact restriction prevents commercial follow-up.')
    if party.relationship=='EXISTING_CUSTOMER':raise HTTPException(409,'Use existing relationship work; duplicate acquisition is suppressed.')
    if prospect_priority(prospect,party,source)[1]=='SOURCE_REVIEW':raise HTTPException(409,'Refresh the permitted source before commercial follow-up.')
    if not prospect.need_reviewed or prospect.disposition:raise HTTPException(409,'Review the current need and disposition before follow-up.')
    cas(db,Prospect,prospect,req.base_version);prospect.state='FOLLOWUP_PLANNED'
    task=Journey(id=uid('FOLLOWUP'),tenant_id=user.tenant_id,party_id=party.id,actor_id=user.user_id,source_id=prospect.source_id,prospect_id=prospect.id,kind='RM_FOLLOWUP',request_key=req.request_key,payload_hash=payload,need=prospect.need,status='PLANNED',operation_ref=uid('RM-TASK'),draft='Draft only — not sent. Prepare a needs discussion with '+party.name+'. Reviewed need: '+prospect.need+' Product applications continue in the bank’s separate menu; NextRM does not open products.')
    db.add(task);db.flush();review_event(db,user,task.id,'FOLLOWUP_PREPARED','Prospect discussion preparation; no onboarding or conversion.',{}, {'status':'PLANNED','source_id':task.source_id});db.commit();return journey_data(db,task)

@router.get('/follow-ups',response_model=RMJourneys)
def followups(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user)
    rows=db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').order_by(Journey.created_at.desc()).all()
    return {'journeys':[journey_data(db,scoped_journey(db,user,x.id)) for x in rows]}

@router.get('/follow-ups/{id}',response_model=RMJourney)
def followup(id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);row=scoped_journey(db,user,id)
    if row.kind!='RM_FOLLOWUP':raise HTTPException(404,'RM follow-up not found.')
    return journey_data(db,row)

@router.post('/follow-ups/{id}',response_model=RMJourney)
def update_followup(id:str,req:RMFollowupUpdate,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);row=scoped_journey(db,user,id);party=party_for(db,user,row.party_id)
    if row.kind!='RM_FOLLOWUP' or row.actor_id!=user.user_id:raise HTTPException(404,'Assigned RM follow-up not found.')
    payload=hash_payload(req.model_dump(exclude={'base_version','request_key'}));history=json.loads(row.history_json)
    old=next((x for x in history if x.get('request_key')==req.request_key),None)
    if old:
        if old.get('payload_hash')!=payload:raise HTTPException(409,'Follow-up action key conflicts.')
        return journey_data(db,row)
    if row.status in {'DONE','CANCELLED'}:raise HTTPException(409,'This follow-up is closed; its history is retained.')
    if req.action in {'NOTE','COMPLETE','CANCEL','SNOOZE'} and len(req.note.strip())<3:raise HTTPException(422,'Record a clear RM note or outcome reason.')
    due=None
    if req.due_at:
        try:
            due=datetime.fromisoformat(req.due_at.replace('Z','+00:00'))
            if due.tzinfo is None:raise ValueError()
            due=stamp(due.astimezone(timezone.utc))
        except ValueError:raise HTTPException(422,'Due time must include a valid timezone.')
    if req.action=='START' and row.status!='PLANNED':raise HTTPException(409,'The follow-up is already in progress.')
    service=bool(row.signal_id and db.query(Signal).filter_by(id=row.signal_id,tenant_id=user.tenant_id,category='SERVICE_ISSUE').first())
    if req.action in {'START','COMPLETE'} and not service and party.contact!='ALLOWED':raise HTTPException(403,'Commercial follow-up is restricted. Notes/cancellation and service help remain available.')
    from ..models.relationships import FollowupDetail
    detail=db.query(FollowupDetail).filter_by(id=row.id,tenant_id=user.tenant_id).first()
    if req.action=='SNOOZE' and (not due or datetime.fromisoformat(due)<=utc_now()):raise HTTPException(422,'Snooze needs a future due time.')
    if req.outcome and req.action!='COMPLETE':raise HTTPException(422,'A structured outcome belongs to recorded completion.')
    before={'status':row.status,'version':row.version};cas(db,Journey,row,req.base_version)
    if req.action=='START':row.status='IN_PROGRESS';row.stage=1
    elif req.action=='COMPLETE':row.status='DONE';row.stage=2
    elif req.action=='CANCEL':row.status='CANCELLED'
    if not detail:
        detail=FollowupDetail(id=row.id,tenant_id=user.tenant_id);db.add(detail)
    if req.action=='SNOOZE':detail.snoozed_until=datetime.fromisoformat(due)
    elif req.action in {'START','COMPLETE','CANCEL'}:detail.snoozed_until=None
    if req.action=='COMPLETE':detail.outcome=req.outcome or 'PREPARATION_RECORDED'
    history.append({'event':req.action,'status':row.status,'at':stamp(utc_now()),'reference':row.operation_ref,'mode':'HUMAN_RECORDED','note':req.note,'due_at':due,'request_key':req.request_key,'payload_hash':payload,'outcome':detail.outcome,'snoozed_until':stamp(detail.snoozed_until) if detail.snoozed_until else None})
    row.history_json=j(history)
    if row.signal_id and req.action=='COMPLETE':
        signal=db.query(Signal).filter_by(id=row.signal_id,tenant_id=user.tenant_id,party_id=row.party_id).first()
        signal.workflow='COMPLETED';signal.version+=1
    # Completing RM work never establishes a customer relationship or product outcome.
    review_event(db,user,row.id,'RM_FOLLOWUP_'+req.action,req.note or 'RM began preparation.',before,{'status':row.status,'due_at':due});db.commit();return journey_data(db,row)

@router.post('/follow-ups/{id}/ai-draft',response_model=RMAIDraft)
def followup_ai_draft(id:str,req:RMAIDraftRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);row=scoped_journey(db,user,id)
    if row.kind!='RM_FOLLOWUP' or row.actor_id!=user.user_id:raise HTTPException(403,'Assigned RM follow-up ownership required.')
    party=party_for(db,user,row.party_id)
    is_service=False
    if row.signal_id:
        sig=db.query(Signal).filter_by(id=row.signal_id,tenant_id=user.tenant_id).first()
        if sig and sig.category=='SERVICE_ISSUE':is_service=True
    if party.contact!='ALLOWED' and not is_service:
        raise HTTPException(409,"Commercial contact is restricted for this customer; service help remains available.")
    source=db.query(Source).filter_by(id=row.source_id,tenant_id=user.tenant_id,party_id=party.id).first()
    if not source:raise HTTPException(409,'Journey source binding requires repair.')
    src_data=source_data(source)
    provider,_=provider_info()
    first_name=party.name.split()[0] if party.name else "Customer"
    constraints=['Commercial contact is permitted; service help available.'] if party.contact=='ALLOWED' else ['Service contact only.']
    started=time.perf_counter()
    try:
        gen=generate_ai_draft(row.need,src_data,party.name,first_name,user.name,req.channel,constraints,provider)
        sources=[RMSource(**src_data)] if source.id in gen['source_ids'] else []
        record_ai_audit_event(db,user,'AI_DRAFT_GENERATED','RM_FOLLOWUP',id,gen['mode'],gen['model'],gen['prompt_version'],gen['latency_ms'],gen['source_ids'])
        db.commit()
        return {'followup_id':id,'subject':gen['subject'],'body':gen['body'],'source_ids':gen['source_ids'],'sources':sources,'mode':gen['mode'],'model':gen['model'],'prompt_version':gen['prompt_version'],'latency_ms':gen['latency_ms'],'generated_at':stamp(utc_now()),'boundary':"Draft only — not sent. Review and send through the bank's official channel."}
    except ProviderUnavailable as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_DRAFT_FAILED','RM_FOLLOWUP',id,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_DRAFT_VERSION,latency_ms,[])
        db.commit()
        msg=str(exc) or 'Configure the requested Google provider, supported GEMINI_MODEL, project/region or server API key.'
        if 'no simulated fallback' not in msg.lower() and 'no local fallback' not in msg.lower():msg+=' No simulated fallback was used.'
        raise HTTPException(503,msg)
    except ProviderFailure as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_DRAFT_FAILED','RM_FOLLOWUP',id,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_DRAFT_VERSION,latency_ms,[])
        db.commit()
        msg=str(exc) or 'Google response was unavailable, timed out or failed validation.'
        if 'no simulated fallback' not in msg.lower() and 'no local fallback' not in msg.lower():msg+=' No simulated fallback was used.'
        raise HTTPException(502,msg)
    except Exception as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_DRAFT_FAILED','RM_FOLLOWUP',id,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_DRAFT_VERSION,latency_ms,[])
        db.commit()
        raise HTTPException(502,'Google response was unavailable, timed out or failed validation; no simulated fallback used.') from exc

@router.get('/pulse',response_model=RMPulse)
def pulse(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user)
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).all();signals.sort(key=priority_key)
    tasks=db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED'])).all()
    data=[journey_data(db,scoped_journey(db,user,x.id)) for x in tasks];now=utc_now().replace(tzinfo=timezone.utc)
    overdue=sum(bool(x['due_at'] and datetime.fromisoformat(x['due_at'])<now) for x in data)
    return {'open_signals':len(signals),'needs_review':sum(x.review=='PROPOSED' for x in signals),'urgent_service':sum(x.category=='SERVICE_ISSUE' and x.urgency in {'URGENT','TIME_SENSITIVE'} for x in signals),'open_followups':len(tasks),'overdue_followups':overdue,'signals':[signal_data(db,scoped_signal(db,user,x.id)) for x in signals[:12]],'followups':data,'method':'Counts from assigned current signals and RM follow-up records. Due dates are RM-entered. No propensity, credit score, product completion or transaction reconciliation is inferred.'}

@router.get('/destinations',response_model=RMDestinations)
def destinations(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    if user.role=='CUSTOMER':party_for(db,user,user.entity_id,customer=True)
    else:require_rm(user)
    return destination_data(user.tenant_id)


def nudge_sources(db,row):
    context=db.query(Source).filter_by(id=row.source_id,tenant_id=row.tenant_id,party_id=row.party_id).first()
    knowledge=db.query(Source).filter_by(id=row.knowledge_id,tenant_id=row.tenant_id,kind='APPROVED_KNOWLEDGE').first()
    if not context:
        from ..models.relationships import SuggestionMeta
        meta=db.query(SuggestionMeta).filter_by(id=row.id,tenant_id=row.tenant_id,family='E08').first()
        if meta:context=db.query(Source).filter_by(id=row.source_id,tenant_id=row.tenant_id,party_id=None,kind='APPROVED_KNOWLEDGE').first()
    if not context or not knowledge:
        raise HTTPException(409,'Suggestion source binding requires repair.')
    return context,knowledge

def nudge_allowed(db,row,party):
    from ..services.enrichment import eligibility
    enriched=eligibility(db,row,party)
    if enriched is not None:
        return not bool(enriched)
    if row.route!='SERVICE' and (party.contact!='ALLOWED' or party.identity!='CONFIRMED'):
        return False
    context,knowledge=nudge_sources(db,row)
    from ..models.relationships import EngagementProfile
    profile=db.query(EngagementProfile).filter_by(tenant_id=party.tenant_id,party_id=party.id).first()
    if profile and context.kind=='SYNTHETIC_CUSTOMER_CONTEXT' and context.content!=json.loads(profile.data_json).get('goal',''):
        return False
    now=utc_now()
    if any(not -300 <= (now-source.event_at.replace(tzinfo=timezone.utc)).total_seconds() <= 30*86400 for source in [context,knowledge]):
        return False
    if row.route!='SERVICE' and db.query(Signal).filter_by(tenant_id=party.tenant_id,party_id=party.id,category='SERVICE_ISSUE').filter(Signal.urgency.in_(['URGENT','TIME_SENSITIVE']),Signal.workflow.notin_(['DISMISSED','COMPLETED'])).first():
        return False
    return True

def nudge_data(db,row):
    context,knowledge=nudge_sources(db,row)
    from ..models.relationships import SuggestionMeta
    meta=db.get(SuggestionMeta,row.id)
    copy_mode=(json.loads(meta.dependencies_json).get('copy') or {}).get('mode') if meta else None
    return {'id':row.id,'party_id':row.party_id,'route':row.route,'title':row.title,'body':row.body,'prompt':row.prompt,'state':row.state,'version':row.version,
            'source':source_data(context),'knowledge':source_data(knowledge),'why':'Based on your stated goal in the permitted customer context. Approved educational information; no purchase intent or financial suitability inferred.',
            'signal_id':row.signal_id,'mode':copy_mode or 'SIMULATED'}

@router.get('/chat/{party_id}/nudges',response_model=RMNudges)
def customer_nudges(party_id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    party=party_for(db,user,party_id,customer=True)
    if party.kind!='PERSON' or party.relationship!='EXISTING_CUSTOMER':
        raise HTTPException(403,'Suggestions require an authorized existing person relationship.')
    rows=db.query(Nudge).filter_by(tenant_id=user.tenant_id,party_id=party.id).filter(Nudge.state!='DISMISSED').order_by(Nudge.id).all()
    return {'nudges':[nudge_data(db,row) for row in rows if nudge_allowed(db,row,party)],'method':'NUDGE-1: declared context and approved knowledge, 30-day freshness, current contact/identity gates, urgent service first. Explore is not intent; only explicit Request RM help with sharing creates a reviewable request.'}

@router.post('/chat/{party_id}/nudges/{id}',response_model=RMNudge)
def nudge_action(party_id:str,id:str,req:RMNudgeAction,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    party=party_for(db,user,party_id,customer=True)
    if party.kind!='PERSON' or party.relationship!='EXISTING_CUSTOMER':
        raise HTTPException(403,'Suggestions require an authorized existing person relationship.')
    row=db.query(Nudge).filter_by(id=id,tenant_id=user.tenant_id,party_id=party.id).first()
    if not row:raise HTTPException(404,'Suggestion not found in your permitted scope.')
    nudge_sources(db,row)
    payload=hash_payload({'nudge':id,**req.model_dump()})
    # A stable request key is retained in append-only events, including private dismissals.
    receipt_id='NUDGE-ACTION-'+hash_payload({'tenant':user.tenant_id,'actor':user.user_id,'key':req.request_key})[:40]
    receipt=db.get(ReviewEvent,receipt_id)
    if receipt:
        if json.loads(receipt.after_json).get('payload_hash')!=payload:raise HTTPException(409,'Suggestion action key conflicts.')
        return nudge_data(db,row)
    if row.state in {'REQUESTED','DISMISSED'}:
        raise HTTPException(409,'This suggestion is closed. Check the recorded request or current suggestions.')
    if req.action!='DISMISS' and not nudge_allowed(db,row,party):
        raise HTTPException(409,'This suggestion is no longer available. Contact, source freshness or service priority changed.')
    from ..models.relationships import SuggestionMeta
    meta=db.query(SuggestionMeta).filter_by(id=row.id,tenant_id=user.tenant_id).first()
    if req.action=='REQUEST_RM' and meta and meta.category=='RECOGNITION':
        raise HTTPException(422,'Recognition is not a commercial opportunity. Ask a separate question for help.')
    if req.action=='REQUEST_RM' and row.route!='SERVICE' and party.contact!='ALLOWED':
        raise HTTPException(403,'Commercial follow-up is off. Explore privately or request service help.')
    if req.action=='REQUEST_RM' and not req.share_with_rm:
        raise HTTPException(422,'Request RM help requires explicit sharing. You can still explore privately.')
    before={'state':row.state,'version':row.version};cas(db,Nudge,row,req.base_version)
    row.state={'EXPLORE':'EXPLORED','DISMISS':'DISMISSED','REQUEST_RM':'REQUESTED'}[req.action]
    if req.action=='REQUEST_RM':
        statement='I would like RM help to discuss: '+row.title+'. This is a request for a conversation, not a product application or purchase.'
        source=Source(id=uid('NUDGE-MSG'),tenant_id=user.tenant_id,party_id=party.id,kind='CUSTOMER_MESSAGE' if user.role=='CUSTOMER' else 'SIMULATED_CUSTOMER_MESSAGE',title='Customer requested help · '+row.title,content=statement,content_hash=hashlib.sha256(statement.encode()).hexdigest(),mode='SIMULATED')
        db.add(source);db.flush()
        signal=Signal(id=uid('SIG'),tenant_id=user.tenant_id,party_id=party.id,source_id=source.id,owner_id=party.owner_id,semantic_key='NUDGE-'+row.id,
                      category='SERVICE_ISSUE' if row.route=='SERVICE' else 'OPPORTUNITY',urgency='ROUTINE',evidence='CUSTOMER_CONFIRMED',title=row.title,
                      need=statement,rationale='Explicit customer request from an in-app suggestion; original context source '+row.source_id+' and approved knowledge '+row.knowledge_id+' retained. No purchase or product outcome inferred.',
                      uncertainty='RM must review the discussion need and clarify goal/timeframe. This request is not consent to unrelated marketing.',confirmed=True)
        db.add(signal);db.flush();row.signal_id=signal.id
    db.add(ReviewEvent(id=receipt_id,tenant_id=user.tenant_id,resource_id=row.id,actor_id=user.user_id,action='NUDGE_'+req.action,
                       reason='Explicit in-app customer choice; no external message sent.',before_json=j(before),after_json=j({'state':row.state,'signal_id':row.signal_id,'payload_hash':payload,'checked_at':stamp(utc_now()),'dependencies':json.loads(meta.dependencies_json) if meta else None})))
    db.commit();return nudge_data(db,row)
