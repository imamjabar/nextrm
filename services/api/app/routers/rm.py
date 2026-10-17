import json,time,os,re
from datetime import timedelta,datetime
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import update,select,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.entities import UserAssignmentModel,utc_now
from ..models.relationships import Party,Source,Prospect,Conversation,Turn,Signal,ReviewEvent,Journey,EvaluationRun
from ..schemas.rm import *
from ..services.rm import *
from ..services.assistant.engine import LOCAL_MODEL,PROMPT_VERSION,respond,provider_info,classify,ProviderUnavailable,ProviderFailure,redact_message,needs_rm_attention
router=APIRouter(prefix='/v1/rm',tags=['relationship-workspace'])

def prospects_data(db,items):
    result=[]
    for x in items:
        party=db.query(Party).filter_by(id=x.party_id,tenant_id=x.tenant_id).first()
        source=db.query(Source).filter_by(id=x.source_id,tenant_id=x.tenant_id,party_id=x.party_id).first()
        if not party or not source:raise HTTPException(409,'Prospect identity/source binding requires repair; no foreign content is returned.')
        if party.owner_id!=x.owner_id:raise HTTPException(409,'Prospect owner binding requires repair; no unassigned relationship content is returned.')
        order,tier,reason,action=prospect_priority(x,party,source)
        task=db.query(Journey).filter_by(tenant_id=x.tenant_id,party_id=x.party_id,prospect_id=x.id,actor_id=x.owner_id,kind='RM_FOLLOWUP').first()
        if task and task.status in {'DONE','CANCELLED'}:
            order,tier,reason,action=3,'FOLLOWUP_RECORDED','RM work is '+task.status.lower()+'. This does not establish a product outcome or customer conversion.','View recorded follow-up'
        text=source.content.casefold()
        explicit=bool(re.search(r'\b(i want|i would like|we would like|please arrange)\b',text)) and not any(v in text for v in ['not interested','do not contact','just researching'])
        knowledge_key='merchant' if any(v in text for v in ['shop','business','collections']) else 'savings' if any(v in text for v in ['saving','emergency fund','salary account']) else None
        approved=knowledge_key and db.query(Source).filter(Source.tenant_id==x.tenant_id,Source.kind=='APPROVED_KNOWLEDGE',Source.id.endswith('KB-'+knowledge_key)).first()
        hot=bool(tier=='READY_FOR_DISCUSSION' and source.kind=='SYNTHETIC_OPT_IN' and explicit and x.need==source.content and approved)
        hot_reason='ACQ-HOT-1: explicit opt-in discussion request, unchanged source-backed need, RM review, current identity/contact/freshness gates and approved educational knowledge. This labels a discussion opportunity, not a person or purchase probability.' if hot else 'Not a hot discussion: explicit current source-backed need and completed RM review are required. Location alone never establishes interest.'
        result.append({'id':x.id,'party':party_data(db,party),'source':source_data(source),'state':x.state,'disposition':x.disposition,'need':x.need,'need_reviewed':x.need_reviewed,'reasons':json.loads(x.reasons_json),'latitude':float(x.latitude),'longitude':float(x.longitude),'version':x.version,'map_mode':'SIMULATED','priority_tier':tier,'priority_reason':reason,'next_action':action,'priority_method':'ACQ-1','hot_lead':hot,'hot_reason':hot_reason,'followup_id':task.id if task else None,'followup_status':task.status if task else None,'_order':order})
    result.sort(key=lambda x:(x['_order'],-datetime.fromisoformat(x['source']['event_at']).timestamp(),x['id']))
    for row in result:row.pop('_order')
    return result

def prospect_for(db,user,id):
    require_rm(user);p=db.query(Prospect).filter_by(id=id,tenant_id=user.tenant_id,owner_id=user.user_id).first()
    if not p:raise HTTPException(404,'Prospect not found in your assignment.')
    return p,party_for(db,user,p.party_id)

@router.get('/home',response_model=RMHome)
def home(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user)
    from ..services.coverage import owned_ids
    parties=db.query(Party).filter(Party.tenant_id==user.tenant_id,Party.relationship=='EXISTING_CUSTOMER',Party.id.in_(owned_ids(db,user))).all()
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).order_by(Signal.created_at.desc()).all()
    signals.sort(key=priority_key)
    prospects=db.query(Prospect).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).all()
    from ..models.banking import BankCustomer
    existing_party_ids={p.id for p in db.query(Party).filter_by(tenant_id=user.tenant_id,relationship='EXISTING_CUSTOMER').all()}
    bank_cust_party_ids={bc.party_id for bc in db.query(BankCustomer).filter(BankCustomer.tenant_id==user.tenant_id,BankCustomer.party_id!=None).all()}
    all_existing_party_ids=existing_party_ids|bank_cust_party_ids
    active_prospects=[x for x in prospects if x.disposition!='EXISTING_CUSTOMER' and x.party_id not in all_existing_party_ids]
    p,ready=provider_info()
    try:quality_grant(db,user);access=True
    except HTTPException:access=False
    return {'customers':len(parties),'prospects':len(active_prospects),'open_signals':len(signals),'open_followups':db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED'])).count(),'open_journeys':db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['COMPLETED','CANCELLED'])).count(),'signals':[signal_data(db,x) for x in signals[:8]],'prospect_preview':[p for p in prospects_data(db,prospects) if p['priority_tier']!='EXISTING_RELATIONSHIP'][:4],'provider':p,'provider_ready':ready,'data_mode':'SYNTHETIC','quality_access':access}

@router.get('/parties',response_model=RMParties)
def parties(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    if user.role=='CUSTOMER':rows=db.query(Party).filter_by(id=user.entity_id,tenant_id=user.tenant_id).all()
    else:
        require_rm(user)
        from ..services.coverage import visible_ids
        rows=db.query(Party).filter(Party.tenant_id==user.tenant_id,Party.id.in_(visible_ids(db,user))).order_by(Party.name).limit(100).all()
    return {'parties':[party_data(db,x) for x in rows]}

@router.get('/signals',response_model=RMSignals)
def signals(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);rows=db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).all();rows.sort(key=priority_key)
    return {'signals':[signal_data(db,x) for x in rows],'parties':[party_data(db,x) for x in db.query(Party).filter(Party.tenant_id==user.tenant_id,Party.relationship=='EXISTING_CUSTOMER',Party.id.in_(__import__('app.services.coverage',fromlist=['visible_ids']).visible_ids(db,user))).limit(100).all()]}

@router.get('/parties/{id}',response_model=RMPartyDetail)
def party_detail(id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,id);staff=user.role=='RM'
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=id).all() if staff else []
    journeys=db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=id,kind='RM_FOLLOWUP')
    journeys=journeys.all()
    linked_prospects=db.query(Prospect).filter_by(tenant_id=user.tenant_id,party_id=id).all() if staff else []
    sourceids={x.source_id for x in signals}|{x.source_id for x in journeys}|{x.source_id for x in linked_prospects}
    sources=db.query(Source).filter(Source.tenant_id==user.tenant_id,Source.id.in_(sourceids)).all() if staff else []
    history=db.query(ReviewEvent).filter(ReviewEvent.tenant_id==user.tenant_id,ReviewEvent.resource_id.in_([id]+[x.id for x in signals]+[x.id for x in journeys]+[x.id for x in linked_prospects])).order_by(ReviewEvent.created_at.desc()).all() if staff else []
    return {'party':party_data(db,p),'signals':[signal_data(db,x) for x in signals],'journeys':[(journey_data(db,x) if staff else customer_journey_data(db,x)) for x in journeys],'sources':[source_data(x) for x in sources],'review_history':[{'id':x.id,'action':x.action,'reason':x.reason,'actor_id':x.actor_id,'before':json.loads(x.before_json),'after':json.loads(x.after_json),'at':stamp(x.created_at)} for x in history],'internal_note':json.loads(p.context_json).get('notes') if staff else None}

@router.get('/sources/{id}',response_model=RMSource)
def source_read(id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    s=db.query(Source).filter_by(id=id,tenant_id=user.tenant_id).first()
    if not s:raise HTTPException(404,'Source not found.')
    if user.role=='RM' and s.kind=='CUSTOMER_MESSAGE' and db.query(Turn).filter(Turn.tenant_id==user.tenant_id,Turn.party_id==s.party_id,Turn.share.is_(False),Turn.output_json.contains('"message_source_id": "'+s.id+'"')).first():raise HTTPException(403,'This historical turn was private to its customer.')
    if s.kind=='PRIVATE_CUSTOMER_MESSAGE' and user.role!='CUSTOMER':raise HTTPException(403,'This turn is private to its customer.')
    if s.kind=='RM_CONTACT_NOTE' and user.role!='RM':raise HTTPException(403,'Contact notes are staff-only.')
    if s.party_id:
        party_for(db,user,s.party_id)
        if user.role=='RM' and s.kind=='CUSTOMER_DECLARED_CONTEXT':
            from ..models.relationships import EngagementProfile
            profile=db.query(EngagementProfile).filter_by(tenant_id=user.tenant_id,party_id=s.party_id).first()
            context=json.loads(profile.data_json) if profile else {}
            if not context.get('share_context') or context.get('source_id')!=s.id:raise HTTPException(403,'This declared context is private or withdrawn from RM sharing.')
    elif s.kind!='APPROVED_KNOWLEDGE':raise HTTPException(403,'Source is restricted.')
    elif user.role not in {'RM','CUSTOMER'}:raise HTTPException(403,'Knowledge access requires the customer or assigned RM surface.')
    return source_data(s)

@router.post('/signals/{id}/review',response_model=RMSignal)
def review_signal(id:str,req:RMReview,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    s=scoped_signal(db,user,id)
    if s.workflow in {'IN_PROGRESS','COMPLETED','DISMISSED'}:
        raise HTTPException(409,'This need is already in follow-up or closed. Retain its review; record new context in the follow-up or a new customer request.')
    if req.decision in {'EDITED','REJECTED'} and len(req.reason)<3:raise HTTPException(422,'A correction or dismissal requires a reason.')
    if req.decision=='EDITED' and not req.need:raise HTTPException(422,'Supply the corrected need.')
    source=db.get(Source,s.source_id)
    if req.confirmed and (source.kind not in {'CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE'} or (req.need is not None and req.need!=s.need)):
        raise HTTPException(422,'Staff review or edited notes cannot substitute for a sourced customer confirmation.')
    before=signal_data(db,s);cas(db,Signal,s,req.base_version)
    s.review=req.decision;s.workflow='DISMISSED' if req.decision=='REJECTED' else 'REVIEWED'
    if req.need:s.need=req.need
    s.confirmed=req.confirmed;s.updated_at=utc_now()
    review_event(db,user,id,req.decision,req.reason or 'Interpretation reviewed; confirmation status explicitly recorded.',before,signal_data(db,s));db.commit();return signal_data(db,s)

@router.post('/parties/{id}/preferences',response_model=RMParty)
def preference(id:str,req:RMPreference,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,id,customer=True);before=party_data(db,p);cas(db,Party,p,req.base_version);p.contact='ALLOWED' if req.commercial_allowed else 'RESTRICTED'
    ctx=json.loads(p.context_json);ctx['contact_reason']=req.reason;p.context_json=j(ctx)
    review_event(db,user,id,'COMMUNICATION_PREFERENCE',req.reason,before,party_data(db,p));db.commit();return party_data(db,p)

@router.get('/prospects',response_model=RMProspects)
def prospects(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);items=db.query(Prospect).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).order_by(Prospect.id).all()
    return {'prospects':prospects_data(db,items),'map_label':'Synthetic locality map · illustrative coordinates; no live map provider'}

@router.post('/prospects/{id}/needs',response_model=RMProspect)
def review_prospect(id:str,req:RMProspectReview,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    x,p=prospect_for(db,user,id)
    if db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=p.id,prospect_id=x.id,kind='RM_FOLLOWUP').first():raise HTTPException(409,'A follow-up already retains this reviewed need. Record further context in its notes or use a new sourced request.')
    if p.identity!='CONFIRMED':raise HTTPException(409,'Identity must remain under review before needs handoff.')
    if p.contact!='ALLOWED':raise HTTPException(403,'Contact/action is restricted. Respect the source preference.')
    if p.relationship=='EXISTING_CUSTOMER':raise HTTPException(409,'This is an existing relationship; suppress duplicate acquisition and use retention work.')
    source=db.query(Source).filter_by(id=x.source_id,tenant_id=user.tenant_id,party_id=p.id).first()
    if not source:raise HTTPException(409,'Prospect source binding requires repair.')
    if prospect_priority(x,p,source)[1]=='SOURCE_REVIEW':raise HTTPException(409,'Refresh the permitted source before reviewing this need.')
    if x.disposition:raise HTTPException(409,'The recorded disposition blocks a new needs review.')
    before={'need':x.need,'reviewed':x.need_reviewed};cas(db,Prospect,x,req.base_version);x.need=req.need;x.need_reviewed=req.confirm;x.state='NEED_REVIEWED' if req.confirm else 'ASSIGNED'
    review_event(db,user,id,'NEED_REVIEW','RM reviewed the stated acquisition need; formal onboarding remains separate.',before,{'need':x.need,'reviewed':x.need_reviewed});db.commit();return prospects_data(db,[x])[0]

@router.post('/prospects/{id}/identity',response_model=RMProspect)
def identity_review(id:str,req:RMIdentityReview,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    x,p=prospect_for(db,user,id)
    # This bounded fixture records unresolved reviews rather than accepting name-only merges.
    if p.identity=='AMBIGUOUS' and req.decision=='CONFIRMED':raise HTTPException(422,'Ambiguous candidates cannot be merged from a note. Use an authorized unique-identifier resolver; unavailable in this local adapter.')
    cas(db,Prospect,x,req.base_version);p.identity=req.decision;p.version+=1
    review_event(db,user,id,'IDENTITY_REVIEW',req.evidence,{}, {'identity':p.identity});db.commit();return prospects_data(db,[x])[0]

@router.post('/prospects/{id}/disposition',response_model=RMProspect)
def disposition(id:str,req:RMDisposition,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    x,p=prospect_for(db,user,id);cas(db,Prospect,x,req.base_version);before={'disposition':x.disposition};x.disposition=req.disposition
    review_event(db,user,id,'DISPOSITION',req.reason,before,{'disposition':x.disposition});db.commit();return prospects_data(db,[x])[0]

@router.get('/chat/{party_id}',response_model=RMConversation)
def chat_history(party_id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,party_id,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'The retail chat requires an authorized existing person relationship.')
    c=db.query(Conversation).filter_by(tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id).first()
    if not c:
        c=Conversation(id=uid('CONV'),tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id);db.add(c)
        try:db.commit()
        except IntegrityError:db.rollback();c=db.query(Conversation).filter_by(tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id).one()
    expired=db.query(Turn).filter(Turn.tenant_id==user.tenant_id,Turn.conversation_id==c.id,Turn.status=='PENDING',Turn.created_at<utc_now()-timedelta(seconds=60)).all()
    for old in expired:old.status='FAILED';old.error_code='INTERRUPTED_REQUEST';old.answer='Response delivery was interrupted or remains unconfirmed. No financial action was taken; a new request may be made after checking this terminal status.'
    if expired:db.commit()
    turns=list(reversed(db.query(Turn).filter_by(tenant_id=user.tenant_id,conversation_id=c.id).order_by(Turn.created_at.desc()).limit(40).all()));provider,ready=provider_info()
    return {'id':c.id,'party':party_data(db,p),'institution_name':user.institution_name,'version':c.version,'turns':[turn_data(db,t) for t in turns],'provider':provider,'provider_ready':ready}

@router.post('/chat/{party_id}/turns',response_model=RMTurn)
def chat_turn(party_id:str,req:RMChatRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    start=time.perf_counter();message=redact_message(req.message);p=party_for(db,user,party_id,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'Retail chat requires an authorized person relationship.')
    from ..services.customer_activity import chat_capture,capture_policy
    capture=chat_capture(user,req.share_with_rm,message)
    payload=hash_payload({'party':party_id,**req.model_dump(exclude={'session_id'} if req.session_id is None else set())})
    existing=db.query(Turn).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,request_key=req.request_key).first()
    if existing:
        if existing.payload_hash!=payload:raise HTTPException(409,'This request key was used for different message content.')
        return turn_data(db,existing)
    recent=db.query(Turn).filter(Turn.tenant_id==user.tenant_id,Turn.actor_id==user.user_id,Turn.created_at>=utc_now()-timedelta(minutes=1)).count()
    if recent>=30:raise HTTPException(429,'Please wait briefly before sending more messages.')
    c=db.query(Conversation).filter_by(tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id).first()
    if not c:raise HTTPException(409,'Open the current conversation before sending.')
    from .sessions import session_for,turns_query
    chat_session=None
    if req.session_id:chat_session,_=session_for(db,user,party_id,req.session_id)
    turn_query=turns_query(db,user,chat_session) if chat_session else db.query(Turn).filter_by(tenant_id=user.tenant_id,conversation_id=c.id)
    if turn_query.filter(Turn.status=='PENDING').first():raise HTTPException(409,'A prior turn is pending. Check its status before sending another message.')
    completed_turns=list(reversed(turn_query.filter(Turn.status=='COMPLETED').order_by(Turn.created_at.desc(),Turn.id.desc()).limit(8).all()))
    history=[{'message':redact_message(t.message),'answer':t.answer} for t in completed_turns]
    previous=completed_turns[-1] if completed_turns else None;previous_route=previous.route if previous else ''
    from ..services.governance import current_decision
    governance_decision=current_decision(db,user.tenant_id,message,previous_route)
    kb=kb_for(db,user.tenant_id);ctx=party_data(db,p);ctx['governance_context']=governance_decision;ctx['history']=history
    from ..models.relationships import EngagementProfile
    from ..services.enrichment import fresh,scoped_source
    profile=db.query(EngagementProfile).filter_by(tenant_id=user.tenant_id,party_id=p.id).first();context_source=None
    if profile:
        declared=json.loads(profile.data_json);ctx['declared_goal']='';ctx['declared_horizon']='';ctx['declared_interests']=[]
        context_source=scoped_source(db,user.tenant_id,p.id,declared.get('source_id'))
        if context_source and fresh(context_source) and __import__('hashlib').sha256(context_source.content.encode()).hexdigest()==context_source.content_hash:
            ctx.update(declared_goal=declared.get('goal',''),declared_horizon=declared.get('horizon',''),declared_interests=declared.get('interests',[]))
        else:context_source=None
    if profile and 'READ_FINANCIAL_CONTEXT' in governance_decision['steps']:
        from ..services.enrichment import insights_for
        financial_start=time.perf_counter();ctx['financial_context']=insights_for(db,p,declared);ctx['financial_context_duration_ms']=int((time.perf_counter()-financial_start)*1000)
    provider,ready=provider_info()
    if not ready:raise HTTPException(503,'Requested AI provider is unavailable. No simulated fallback was used.')
    if chat_session and not chat_session.id.startswith('LEGACY-'):
        from ..models.relationships import ChatSession
        cas(db,ChatSession,chat_session,req.base_version);cas(db,Conversation,c,c.version)
    else:cas(db,Conversation,c,req.base_version)
    t=Turn(id=uid('TURN'),tenant_id=user.tenant_id,conversation_id=c.id,party_id=p.id,actor_id=user.user_id,request_key=req.request_key,payload_hash=payload,message=message,share=capture,mode='SIMULATED' if provider=='local' else 'LIVE',model=LOCAL_MODEL if provider=='local' else os.getenv('GEMINI_MODEL',''))
    db.add(t);db.flush()
    if chat_session and not chat_session.id.startswith('LEGACY-'):
        from ..models.relationships import SessionTurn
        db.add(SessionTurn(id=t.id,tenant_id=user.tenant_id,session_id=chat_session.id))
        if chat_session.title=='New conversation':chat_session.title=message[:70]
        chat_session.updated_at=utc_now()
    if not chat_session or chat_session.id.startswith('LEGACY-'):
        from ..models.relationships import ChatSession
        legacy=db.query(ChatSession).filter_by(id='LEGACY-'+c.id,tenant_id=user.tenant_id,actor_id=user.user_id).first()
        if legacy:legacy.updated_at=utc_now()
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Message changed while sending; reload the original conversation.')
    try:
        try:answer=respond(message,previous_route,kb,ctx,history)
        except TypeError:answer=respond(message,previous_route,kb,ctx)
    except (ProviderUnavailable,ProviderFailure) as e:
        t.status='FAILED';t.error_code='PROVIDER_UNAVAILABLE' if isinstance(e,ProviderUnavailable) else 'MODEL_VALIDATION_OR_TIMEOUT';t.answer='I could not answer that reliably. You can rephrase, or ask for your RM through the official channel.';t.output_json=j({'source_ids':[],'error':str(e)});t.latency_ms=int((time.perf_counter()-start)*1000);db.commit();return turn_data(db,t)
    membership=db.query(UserAssignmentModel).filter_by(user_id=user.user_id,tenant_id=user.tenant_id,active=True).first()
    if not membership:t.status='FAILED';t.error_code='ACCESS_CHANGED';db.commit();raise HTTPException(403,'Access changed during response generation.')
    db.refresh(p);db.refresh(t)
    if t.status!='PENDING':return turn_data(db,t)
    if membership.role!=user.role or (user.role=='RM' and p.owner_id!=user.user_id) or (user.role=='CUSTOMER' and membership.entity_id!=p.id):
        t.status='FAILED';t.error_code='ACCESS_CHANGED';db.commit();raise HTTPException(403,'Assignment changed during response generation.')
    text=message.casefold()
    refused=any(x in text for x in ["don't contact",'do not contact','stop contacting','no marketing','unsubscribe'])
    if refused:
        p.contact='RESTRICTED';p.version+=1;review_event(db,user,p.id,'CUSTOMER_REFUSAL','Customer explicitly declined commercial follow-up.',{}, {'contact':'RESTRICTED','turn_id':t.id})
    source=Source(id=uid('MSG'),tenant_id=user.tenant_id,party_id=p.id,kind=('CUSTOMER_MESSAGE' if capture else 'PRIVATE_CUSTOMER_MESSAGE') if user.role=='CUSTOMER' else 'SIMULATED_CUSTOMER_MESSAGE',title='Customer conversation · '+p.name,content=message,content_hash=__import__('hashlib').sha256(message.encode()).hexdigest(),mode='SIMULATED')
    db.add(source);db.flush();signalid=None
    actionable=needs_rm_attention(message,answer)
    capture=chat_capture(user,req.share_with_rm,message)
    allowed_signal=capture and 'PROPOSE_SIGNAL' in governance_decision['steps'] and actionable and answer.category and (p.contact=='ALLOWED' or answer.category=='SERVICE_ISSUE') and not refused
    if allowed_signal:
        key=answer.route+'-'+hash_payload(message.strip().casefold())[:20]
        sig=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=p.id,semantic_key=key).first()
        if sig and sig.workflow in {'COMPLETED','DISMISSED'}:key+='-'+t.id[-8:];sig=None
        if not sig:
            sig=Signal(id=uid('SIG'),tenant_id=user.tenant_id,party_id=p.id,source_id=source.id,turn_id=t.id,owner_id=__import__('app.services.coverage',fromlist=['routing_owner']).routing_owner(db,p,escalate=answer.category=='SERVICE_ISSUE' or __import__('app.services.assistant.engine',fromlist=['human_help_requested']).human_help_requested(message)),semantic_key=key,category=answer.category,urgency=answer.urgency,evidence='CUSTOMER_CONFIRMED' if answer.confirmed else 'OBSERVED',title={'LOAN':'Loan menu help needed' if answer.category=='SERVICE_ISSUE' else 'Loan needs discussion','SERVICE':'Payment status needs help','CARD':'Card service needs attention','WEALTH':'Customer goal needs guidance','SAVINGS':'Savings conversation','DEPOSIT':'Deposit / liquidity conversation','MERCHANT':'Business collections discussion'}.get(answer.route,'Customer question'),need=answer.need or message,rationale='Customer message supports this specific reviewable task; no purchase probability or financial authority inferred.',uncertainty='Needs and permitted next action require RM review; no product activation or transaction result is inferred.',confirmed=answer.confirmed)
            db.add(sig)
        elif sig.review=='PROPOSED' and sig.workflow!='IN_PROGRESS':sig.source_id=source.id;sig.turn_id=t.id;sig.version+=1;sig.updated_at=utc_now()
        signalid=sig.id
    sharing_status='SHARED' if signalid else 'PRIVATE' if not capture else 'CONTACT_PREFERENCE' if refused else 'HELP_ONLY' if not actionable or not answer.category else 'CONTACT_RESTRICTED'
    out_payload={'source_ids':[x['id'] for x in answer.sources],'claims':answer.claims,'signal_id':signalid,'message_source_id':source.id,'model_calls':0 if provider=='local' else 1,'schema_version':'rm-turn-v2','prompt_version':PROMPT_VERSION,'context_source_id':context_source.id if context_source else None,'context_source_version':context_source.version if context_source else None,'context_source_hash':context_source.content_hash if context_source else None,'financial_source_refs':[{'id':x['source']['id'],'version':x['source']['version'],'hash':x['source']['hash']} for x in ctx.get('financial_context',[]) if x.get('source') and x['status']!='UNAVAILABLE'],'governance':governance_decision,'session_id':req.session_id,'signal_policy_version':'ENGAGEMENT-4','capture_policy_version':capture_policy(user)['version'],'capture_method':'INSTITUTION_POLICY' if req.share_with_rm is None else 'EXPLICIT_LEGACY_CHOICE','sharing_status':sharing_status}
    if getattr(answer,'route_mismatch',None):out_payload['route_mismatch']=answer.route_mismatch
    if answer.suggestions:out_payload['suggestions']=answer.suggestions
    t.answer=answer.text;t.route=answer.route;t.status='COMPLETED';t.tools_json=j(answer.tools);t.output_json=j(out_payload)
    db.commit();t.latency_ms=max(1,int((time.perf_counter()-start)*1000));db.commit();return turn_data(db,t)

@router.get('/journeys',response_model=RMJourneys)
def journeys(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    if user.role=='CUSTOMER':rows=db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=user.entity_id,kind='RM_FOLLOWUP').all()
    else:
        require_rm(user);rows=db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').order_by(Journey.created_at.desc()).all()
    return {'journeys':[(customer_journey_data(db,x) if user.role=='CUSTOMER' else journey_data(db,x)) for x in rows]}

@router.get('/journeys/{id}',response_model=RMJourney)
def journey(id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    x=scoped_journey(db,user,id)
    if x.kind!='RM_FOLLOWUP':raise HTTPException(404,'Historical destination workflow is outside active NextRM.')
    return customer_journey_data(db,x) if user.role=='CUSTOMER' else journey_data(db,x)
@router.get('/quality',response_model=RMQuality)
def quality(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.rm_evaluations import quality_summary
    return quality_summary(db,user)

@router.post('/evaluations',response_model=RMEvalRun)
def start_eval(req:RMEvalStart,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.rm_evaluations import eval_data,SUITE_VERSION
    quality_grant(db,user);provider,ready=provider_info()
    if not ready:raise HTTPException(503,'Selected evaluator provider is not configured; no fake score or fallback.')
    old=db.query(EvaluationRun).filter_by(tenant_id=user.tenant_id,request_key=req.request_key).first()
    if old:return eval_data(old)
    if db.query(EvaluationRun).filter(EvaluationRun.tenant_id==user.tenant_id,EvaluationRun.status.in_(['QUEUED','RUNNING'])).count():raise HTTPException(409,'A suite is already queued or running for this institution.')
    from ..services.rm_evaluations import ROOT
    from ..services.governance import released
    definition,release_id,release_version=released(db,user.tenant_id)
    config={'governance_definition':definition,'governance_release':release_id,'governance_version':release_version,'provider':provider,'model':os.getenv('GEMINI_MODEL','') if provider!='local' else LOCAL_MODEL,'prompt_version':PROMPT_VERSION,'knowledge':kb_for(db,user.tenant_id),'cases':json.loads((ROOT/'data/synthetic/rm/evaluation.json').read_text())[:24]}
    run=EvaluationRun(id=uid('EVAL'),tenant_id=user.tenant_id,actor_id=user.user_id,request_key=req.request_key,suite_version=SUITE_VERSION,config_json=j(config),mode='SIMULATED' if provider=='local' else 'LIVE');db.add(run);db.commit();return eval_data(run)

@router.post('/evaluations/{id}/adjudicate',response_model=RMEvalRun)
def adjudicate(id:str,req:RMAdjudication,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.rm_evaluations import eval_data
    grant=quality_grant(db,user)
    if not grant.content:raise HTTPException(403,'A content-review grant is required to adjudicate.')
    run=db.query(EvaluationRun).filter_by(id=id,tenant_id=user.tenant_id,status='COMPLETED').first()
    if not run:raise HTTPException(404,'Completed run not found.')
    results=json.loads(run.results_json);case=next((x for x in results if x['case_id']==req.case_id),None)
    if not case:raise HTTPException(404,'Evaluation case not found.')
    cas(db,EvaluationRun,run,req.base_version);old=dict(case);case['qa_pass']=req.qa_correct;case['reason']='Human adjudication: '+req.reason
    review_event(db,user,id,'QUALITY_ADJUDICATION',req.reason,old,case);run.results_json=j(results);run.updated_at=utc_now();db.commit();return eval_data(run)

@router.post('/imports',response_model=RMImportReceipt)
def import_prospects(req:RMImportRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.rm_import import import_csv
    return import_csv(db,user,req.csv_text,req.request_key)

@router.get('/chat/{party_id}/progress',response_model=RMJourneys)
def customer_progress(party_id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,party_id,customer=True)
    rows=db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=p.id).order_by(Journey.created_at.desc()).limit(10).all()
    return {'journeys':[customer_journey_data(db,x) for x in rows if x.kind=='RM_FOLLOWUP']}

@router.get('/chat/{party_id}/requests',response_model=RMCustomerRequests)
def customer_requests(party_id:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,party_id,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'An existing personal customer relationship is required.')
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=p.id).order_by(Signal.created_at.desc()).limit(40).all()
    result=[]
    for signal in signals:
        source=db.query(Source).filter_by(id=signal.source_id,tenant_id=user.tenant_id,party_id=p.id).first()
        if not source:raise HTTPException(409,'Request source binding requires repair.')
        if source.kind not in {'CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE'}:continue
        task=db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=p.id,signal_id=signal.id,kind='RM_FOLLOWUP').first()
        state='CLOSED' if signal.workflow=='DISMISSED' else 'REVIEWED' if signal.review in {'ACCEPTED','EDITED'} else 'AWAITING_REVIEW'
        due=None;updated=stamp(signal.updated_at)
        if task:
            public=customer_journey_data(db,task);due=public.get('due_at')
            state={'PLANNED':'FOLLOWUP_PLANNED','IN_PROGRESS':'RM_PREPARING','DONE':'RM_WORK_RECORDED','CANCELLED':'CLOSED'}.get(task.status,state)
            history=json.loads(task.history_json);updated=history[-1]['at'] if history else stamp(task.created_at)
        result.append({'id':signal.id,'message':source.content,'status':state,'created_at':stamp(source.event_at),'updated_at':updated,'due_at':due,'mode':source.mode})
    return {'requests':result,'boundary':'RM preparation and work status only. No product opening, purchase, transaction outcome or external service resolution is inferred. Internal RM notes and drafts are excluded.'}
