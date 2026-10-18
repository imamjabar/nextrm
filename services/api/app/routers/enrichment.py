"""Customer-controlled targeting and RM preparation. No outbound/financial tools."""
import json,hashlib,time,os
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.entities import utc_now
from ..models.relationships import *
from ..schemas.rm import *
from ..services.rm import party_for,require_rm,quality_grant,cas,uid,j,stamp,hash_payload,source_data,scoped_journey,priority_key,prospect_priority,record_ai_audit_event
from ..services.assistant.engine import generate_ai_brief,provider_info,ProviderUnavailable,ProviderFailure,PROMPT_BRIEF_VERSION
from ..services.enrichment import profile_for,profile_data,make_source,feed,eligibility,fresh,scoped_source,METHOD
router=APIRouter(prefix='/v1/rm',tags=['engagement-enrichment'])

def customer(db,user,pid):
    p=party_for(db,user,pid,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'An own person relationship is required.')
    return p

def replay(db,user,pid,key,payload):
    old=db.query(EngagementFeedback).filter_by(tenant_id=user.tenant_id,party_id=pid,request_key=key).first()
    if old and old.payload_hash!=payload:raise HTTPException(409,'Choice request key conflicts with the original operation.')
    return json.loads(old.result_json) if old else None

def receipt(db,user,pid,key,payload,action,result,nudge=None):
    row=EngagementFeedback(id=uid('CHOICE'),tenant_id=user.tenant_id,party_id=pid,nudge_id=nudge,action=action,request_key=key,payload_hash=payload,result_json='{}')
    db.add(row);db.flush();result['id']=row.id;row.result_json=j(result);db.commit();return result

@router.get('/chat/{pid}/engagement',response_model=RMEngagementFeed)
def engagement(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    return feed(db,customer(db,user,pid),user)

@router.post('/chat/{pid}/context',response_model=RMEngagementProfile)
def context(pid:str,req:RMContextUpdate,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=customer(db,user,pid);payload=hash_payload(req.model_dump());old=replay(db,user,pid,req.request_key,payload)
    if old:return old['profile']
    if any(x not in {'goals','liquidity','travel','product_help','service','spending'} for x in req.interests):raise HTTPException(422,'Choose supported interest topics.')
    row=profile_for(db,p);cas(db,EngagementProfile,row,req.base_version);d=json.loads(row.data_json)
    source=make_source(db,p,'Customer-declared goal and interests',j({'goal':req.goal,'horizon':req.horizon,'interests':req.interests,'shared_with_rm':req.share_context}))
    d.update(goal=req.goal,horizon=req.horizon,interests=sorted(set(req.interests)),share_context=req.share_context,source_id=source.id)
    row.data_json=j(d);row.updated_at=utc_now();result=profile_data(row,p)
    receipt(db,user,pid,req.request_key,payload,'CONTEXT_UPDATED',{'profile':result})
    return result

@router.post('/chat/{pid}/feedback',response_model=RMFeedbackReceipt)
def feedback(pid:str,req:RMFeedbackRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=customer(db,user,pid);payload=hash_payload(req.model_dump());old=replay(db,user,pid,req.request_key,payload)
    if old:return old
    row=profile_for(db,p);d=json.loads(row.data_json);nudge=None;meta=None
    if req.nudge_id:
        nudge=db.query(Nudge).filter_by(id=req.nudge_id,tenant_id=user.tenant_id,party_id=pid).first()
        meta=db.query(SuggestionMeta).filter_by(id=req.nudge_id,tenant_id=user.tenant_id).first()
        if not nudge or not meta:raise HTTPException(404,'Suggestion not found in your scope.')
    elif req.action!='OPT_OUT':raise HTTPException(422,'Choose a current suggestion for this feedback.')
    if nudge and req.action in {'HELPFUL','EXPOSED'} and eligibility(db,nudge,p,row):raise HTTPException(409,'Refresh the current suggestions before responding.')
    if req.action!='EXPOSED':cas(db,EngagementProfile,row,req.base_version)
    if req.action=='DISMISS':
        if nudge.state=='REQUESTED':raise HTTPException(409,'A shared request is retained. Manage it through a new question.')
        nudge.state='DISMISSED';nudge.version+=1
    if req.action in {'SNOOZE','NOT_RELEVANT'}:
        d.setdefault('snoozes',{})[meta.topic]=stamp(utc_now()+timedelta(days=req.days if req.action=='SNOOZE' else 30))
    if req.action=='OPT_OUT':p.contact='RESTRICTED';p.version+=1
    row.data_json=j(d);row.updated_at=utc_now()
    message={'HELPFUL':'Feedback saved. This is not purchase intent.','NOT_RELEVANT':'Similar topic suggestions paused for 30 days.','SNOOZE':'Topic paused for '+str(req.days)+' days.','DISMISS':'This suggestion dismissed. Other topics remain available.','OPT_OUT':'Commercial follow-up is off. Service and factual help remain available.','EXPOSED':'In-app display recorded; no outbound message sent.'}[req.action]
    return receipt(db,user,pid,req.request_key,payload,req.action,{'action':req.action,'profile_version':row.version,'message':message},req.nudge_id)

@router.get('/parties/{pid}/brief',response_model=RMBrief)
def brief(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);p=party_for(db,user,pid);facts=[];timeline=[];questions=['What would be useful to discuss?','What timing and access constraints matter?'];constraints=['No external action or message is performed by NextRM.'];source_review=False
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=pid,owner_id=user.user_id).all();signals.sort(key=priority_key)
    for s in signals:
        src=scoped_source(db,user.tenant_id,pid,s.source_id)
        if not src:raise HTTPException(409,'Signal source binding needs repair.')
        kind='CUSTOMER_STATEMENT' if src.kind in {'CUSTOMER_MESSAGE','SIMULATED_CUSTOMER_MESSAGE','CUSTOMER_RM_REQUEST'} else 'OBSERVED_EVENT'
        facts.append({'kind':kind,'text':src.content,'source':source_data(src)})
        if s.need!=src.content:facts.append({'kind':'RM_INTERPRETATION','text':s.need,'source':source_data(src)})
        timeline.append({'kind':kind,'text':src.content,'source':source_data(src)})
        source_review=source_review or not fresh(src)
    profile=db.query(EngagementProfile).filter_by(tenant_id=user.tenant_id,party_id=pid).first()
    if profile:
        d=json.loads(profile.data_json)
        if d.get('share_context'):
            src=scoped_source(db,user.tenant_id,pid,d.get('source_id'))
            if src:
                text='Declared goal: '+d.get('goal','Not stated')+'. Horizon: '+d.get('horizon','Not stated')+'. Interests: '+', '.join(d.get('interests',[]))
                facts.append({'kind':'SHARED_CUSTOMER_CONTEXT','text':text,'source':source_data(src)});timeline.append({'kind':'SHARED_CUSTOMER_CONTEXT','text':text,'source':source_data(src)})
                constraints.append('Use only the goal and constraints the customer shared; ask before assuming an amount.')
        if d.get('financial_source_id'):
            fsrc=scoped_source(db,user.tenant_id,pid,d.get('financial_source_id'))
            if fsrc:facts.append({'kind':'OBSERVED_EVENT','text':f"{fsrc.title}: Verified core-banking activity and financial features available.",'source':source_data(fsrc)})
    prospects=db.query(Prospect).filter_by(tenant_id=user.tenant_id,party_id=pid,owner_id=user.user_id).all()
    next_action='Review the original request before preparing a follow-up.'
    for prospect in prospects:
        src=scoped_source(db,user.tenant_id,pid,prospect.source_id)
        if not src:raise HTTPException(409,'Prospect source binding needs repair.')
        facts.append({'kind':'PROSPECT_SOURCE','text':src.content,'source':source_data(src)})
        _,tier,reason,next_action=prospect_priority(prospect,p,src)
        source_review=source_review or tier=='SOURCE_REVIEW'
        questions=['Which part of the sourced enquiry is still a current need?','Who is authorized to discuss it, for which purpose?','What existing process and timing should the RM understand?']
        constraints.append(reason)
    ctx=json.loads(p.context_json)
    if ctx.get('notes'):facts.append({'kind':'INTERNAL_RM_NOTE','text':ctx['notes'],'source':None})
    if p.contact!='ALLOWED':constraints.append('Commercial action is restricted; requested service help remains available.')
    if p.kind=='ORGANIZATION':constraints.append('Contact roles do not establish signing authority or personal-account access.')
    contacts=db.query(ContactRecord).filter_by(tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id).order_by(ContactRecord.occurred_at.desc()).all()
    for c in contacts[:20]:
        src=scoped_source(db,user.tenant_id,pid,c.source_id)
        if not src:raise HTTPException(409,'Contact source binding needs repair.')
        timeline.append({'kind':'HUMAN_RECORDED_ACTIVITY','text':c.event+': '+c.note,'source':source_data(src)})
    timeline.sort(key=lambda x:x['source']['event_at'] if x['source'] else '',reverse=True)
    open_signals=[s for s in signals if s.workflow not in {'COMPLETED','DISMISSED'}]
    why=open_signals[0].title if open_signals else 'Inspect the sourced prospect enquiry.' if prospects else 'Clarify the current need; no urgency is assumed.'
    constraints.append('Customer app conversations are with the banking assistant. Prepare official email/phone outreach; there is no in-app RM messenger.')
    return {'party_id':pid,'why_now':why,'facts':facts,'questions':questions,'constraints':constraints,'next_action':next_action,'contacts':[contact_data(c) for c in contacts[:20]],'timeline':timeline[:30],'source_review':source_review,'method':'RM-BRIEF-1: original evidence, reviewed interpretation and human notes remain distinct; no generated financial advice.'}

@router.post('/parties/{pid}/ai-brief',response_model=RMAIBrief)
def party_ai_brief(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);p=party_for(db,user,pid);b=brief(pid,db,user)
    available_sources={}
    for f in b.get('facts',[]):
        if f.get('source'):available_sources[f['source']['id']]=f['source']
    for t in b.get('timeline',[]):
        if t.get('source'):available_sources[t['source']['id']]=t['source']
    ctx=json.loads(p.context_json)
    if ctx.get('notes'):
        available_sources['rm-note']={'id':'rm-note','title':'Internal RM Note','content':ctx['notes'],'kind':'RM_NOTE','mode':'LOCAL','version':1,'hash':hashlib.sha256(ctx['notes'].encode()).hexdigest(),'event_at':stamp(utc_now()),'ingested_at':stamp(utc_now())}
    provider,_=provider_info()
    started=time.perf_counter()
    try:
        gen=generate_ai_brief(pid,b['why_now'],b['facts'],b['questions'],b['constraints'],b['timeline'],available_sources,provider)
        sources=[RMSource(**available_sources[sid]) for sid in gen['cited_source_ids'] if sid in available_sources]
        record_ai_audit_event(db,user,'AI_BRIEF_GENERATED','PARTY',pid,gen['mode'],gen['model'],gen['prompt_version'],gen['latency_ms'],gen['cited_source_ids'])
        db.commit()
        return {'party_id':pid,'summary':gen['summary'],'talking_points':gen['talking_points'],'questions':gen['questions'],'cautions':gen['cautions'],'sources':sources,'mode':gen['mode'],'model':gen['model'],'prompt_version':gen['prompt_version'],'latency_ms':gen['latency_ms'],'generated_at':stamp(utc_now()),'method':'RM-AI-BRIEF-1: Gemini relationship brief grounded in scoped customer facts and pinned sources; citations verified, numbers cross-checked.'}
    except ProviderUnavailable as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_BRIEF_FAILED','PARTY',pid,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_BRIEF_VERSION,latency_ms,[])
        db.commit()
        msg=str(exc) or 'Configure the requested Google provider, supported GEMINI_MODEL, project/region or server API key.'
        if 'no simulated fallback' not in msg.lower() and 'no local fallback' not in msg.lower():msg+=' No simulated fallback was used.'
        raise HTTPException(503,msg)
    except ProviderFailure as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_BRIEF_FAILED','PARTY',pid,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_BRIEF_VERSION,latency_ms,[])
        db.commit()
        msg=str(exc) or 'Google response was unavailable, timed out or failed validation.'
        if 'no simulated fallback' not in msg.lower() and 'no local fallback' not in msg.lower():msg+=' No simulated fallback was used.'
        raise HTTPException(502,msg)
    except Exception as exc:
        latency_ms=max(1,int((time.perf_counter()-started)*1000))
        record_ai_audit_event(db,user,'AI_BRIEF_FAILED','PARTY',pid,'LIVE',os.getenv('GEMINI_MODEL','vertex'),PROMPT_BRIEF_VERSION,latency_ms,[])
        db.commit()
        raise HTTPException(502,'Google response was unavailable, timed out or failed validation; no simulated fallback used.') from exc

def contact_data(c):return {k:getattr(c,k) for k in ['id','channel','purpose','event','note','source_id']}|{'occurred_at':stamp(c.occurred_at)}

@router.post('/parties/{pid}/contacts',response_model=RMContactRecord)
def record_contact(pid:str,req:RMContactRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);p=party_for(db,user,pid);payload=hash_payload(req.model_dump())
    old=db.query(ContactRecord).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,request_key=req.request_key).first()
    if old:
        if old.payload_hash!=payload:raise HTTPException(409,'Contact action key conflicts.')
        return contact_data(old)
    if p.contact!='ALLOWED' and req.purpose!='SERVICE':raise HTTPException(403,'Commercial contact is restricted.')
    if p.identity!='CONFIRMED' and req.purpose!='SERVICE':raise HTTPException(409,'Resolve identity before preparing a discussion.')
    try:
        occurred=datetime.fromisoformat(req.occurred_at.replace('Z','+00:00'))
        if occurred.tzinfo is None or occurred>utc_now()+timedelta(minutes=5):raise ValueError()
    except ValueError:raise HTTPException(422,'Record a valid past/current time including timezone.')
    cas(db,Party,p,req.base_version)
    src=make_source(db,p,'Human-recorded contact activity',req.note,'RM_CONTACT_NOTE');src.event_at=occurred.astimezone(timezone.utc)
    row=ContactRecord(id=uid('CONTACT'),tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id,source_id=src.id,channel=req.channel,purpose=req.purpose,event=req.event,note=req.note,occurred_at=occurred.astimezone(timezone.utc),request_key=req.request_key,payload_hash=payload)
    db.add(row);db.commit();return contact_data(row)

@router.get('/quality/engagement',response_model=RMEngagementAudit)
def audit(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    grant=quality_grant(db,user);allowed=json.loads(grant.party_scope_json)
    decisions=db.query(EngagementDecision).filter_by(tenant_id=user.tenant_id)
    feedback=db.query(EngagementFeedback).filter_by(tenant_id=user.tenant_id)
    if allowed:decisions=decisions.filter(EngagementDecision.party_id.in_(allowed));feedback=feedback.filter(EngagementFeedback.party_id.in_(allowed))
    rows=decisions.order_by(EngagementDecision.created_at.desc()).limit(60).all();choices=feedback.all()
    # Metadata contains rule IDs/reasons only. No customer names, raw goals or content.
    exposure_ids={x.nudge_id for x in choices if x.action=='EXPOSED'};positive_ids={x.nudge_id for x in choices if x.action=='HELPFUL'};negative_ids={x.nudge_id for x in choices if x.action=='NOT_RELEVANT'}
    responded=positive_ids|negative_ids
    metrics=[{'label':'Helpful suggestions among responses','numerator':len(positive_ids-negative_ids),'denominator':len(responded),'unit':'distinct suggestions with helpful/not-relevant feedback','method':'ENG-METRIC-1; cumulative tenant/grant scope, both-choice conflicts excluded from helpful numerator; missing feedback is separate, not positive.'},
    {'label':'Exposed suggestions with feedback','numerator':len(exposure_ids&responded),'denominator':len(exposure_ids),'unit':'distinct explicitly displayed suggestions','method':'Explicit in-app display receipts, not selections or outbound deliveries. Cumulative scope; no causal uplift claim.'}]
    missing=exposure_ids-responded
    metrics.append({'label':'Exposed suggestions without feedback','numerator':len(missing),'denominator':len(exposure_ids),'unit':'distinct displayed suggestions','method':'Cumulative explicit displays with no helpful/not-relevant response. Missing feedback is neither favorable nor unfavorable.'})
    nudges=db.query(Nudge).join(SuggestionMeta,SuggestionMeta.id==Nudge.id).filter(Nudge.tenant_id==user.tenant_id,Nudge.signal_id.isnot(None))
    if allowed:nudges=nudges.filter(Nudge.party_id.in_(allowed))
    shared=nudges.all();reviewed=sum(bool(db.query(Signal).filter_by(id=n.signal_id,tenant_id=user.tenant_id,party_id=n.party_id).filter(Signal.review.in_(['ACCEPTED','EDITED','REJECTED'])).first()) for n in shared)
    metrics.append({'label':'Shared nudge requests reviewed by RM','numerator':reviewed,'denominator':len(shared),'unit':'explicit shared suggestion requests','method':'Cumulative actual RM review records including rejection. Does not establish relevance, purchase or bank completion.'})
    return {'decisions':[{'id':x.id,'at':stamp(x.created_at),'method':METHOD,'rule_version':'ENGAGE-1','content_version':'ENGAGE-COPY-1','items':json.loads(x.data_json)['items']} for x in rows],'metrics':metrics,'method':'Cumulative recorded decisions/choices in the current institution and explicit grant scope. No financial conversion, estimated ROI or universal quality score.'}

@router.post('/chat/{pid}/category',response_model=RMFeedbackReceipt)
def category_correction(pid:str,req:RMCategoryCorrection,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=customer(db,user,pid);payload=hash_payload(req.model_dump());old=replay(db,user,pid,req.request_key,payload)
    if old:return old
    from ..services.enrichment import insights_for
    row=profile_for(db,p);d=json.loads(row.data_json)
    spend=next((c for c in insights_for(db,p,d) if c['key']=='spending' and c['status']=='AVAILABLE' and c.get('source')),None)
    source=scoped_source(db,user.tenant_id,pid,spend['source']['id']) if spend else None
    if not source or source.id!=req.source_id or source.version!=req.source_version or source.content_hash!=req.source_hash or not fresh(source,86400):raise HTTPException(409,'The financial snapshot changed or is unavailable. Inspect current evidence before correcting.')
    cas(db,EngagementProfile,row,req.base_version)
    return receipt(db,user,pid,req.request_key,payload,'CATEGORY_CORRECTION',{'action':'CATEGORY_CORRECTION','profile_version':row.version,'message':'Your category correction is recorded separately from the original source. It is not automatic training truth.','category':req.category,'source_id':source.id,'source_version':source.version,'source_hash':source.content_hash})
