"""Persistent own-customer sessions; legacy turns remain in their original table."""
import json
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,or_,and_,case
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.relationships import Conversation,Turn,ChatSession,SessionTurn
from ..models.entities import utc_now
from ..schemas.rm import RMNewSession,RMChatSession,RMChatSessions,RMConversation,RMChatMemory
from ..services.rm import party_for,uid,stamp,turn_data,party_data
from ..services.assistant.engine import provider_info
router=APIRouter(prefix='/v1/rm',tags=['customer-chat-sessions'])

def legacy_for(db,user,pid):
    conv=db.query(Conversation).filter_by(tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id).first()
    if not conv:return None,None
    id='LEGACY-'+conv.id;s=db.query(ChatSession).filter_by(id=id,tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id).first()
    if not s:
        s=ChatSession(id=id,tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id,title='Earlier conversation',request_key='legacy-'+conv.id,created_at=conv.created_at,updated_at=conv.created_at);db.add(s);db.flush()
    return s,conv

def session_for(db,user,pid,id):
    p=party_for(db,user,pid,customer=True)
    s=db.query(ChatSession).filter_by(id=id,tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id,archived=False).first()
    if not s:raise HTTPException(404,'Chat session not found in your own account.')
    return s,p

def turns_query(db,user,s):
    if s.id.startswith('LEGACY-'):
        return db.query(Turn).filter_by(tenant_id=user.tenant_id,party_id=s.party_id,actor_id=user.user_id,conversation_id=s.id[len('LEGACY-'):]).filter(~Turn.id.in_(db.query(SessionTurn.id).filter_by(tenant_id=user.tenant_id)))
    return db.query(Turn).join(SessionTurn,SessionTurn.id==Turn.id).filter(Turn.tenant_id==user.tenant_id,Turn.party_id==s.party_id,Turn.actor_id==user.user_id,SessionTurn.session_id==s.id)

def data(db,user,s):
    query=turns_query(db,user,s);count=query.count();last=query.order_by(Turn.created_at.desc(),Turn.id.desc()).first();c=db.query(Conversation).filter_by(id=s.id[len('LEGACY-'):],tenant_id=user.tenant_id).first() if s.id.startswith('LEGACY-') else None
    return {'id':s.id,'title':s.title,'version':c.version if c else s.version,'created_at':stamp(s.created_at),'updated_at':stamp(last.created_at if s.id.startswith('LEGACY-') and last else s.updated_at),'turn_count':count,'legacy':s.id.startswith('LEGACY-')}

@router.get('/chat/{pid}/sessions',response_model=RMChatSessions)
def sessions(pid:str,cursor:str='',db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,pid,customer=True);legacy,conv=legacy_for(db,user,p.id)
    q=db.query(ChatSession).filter_by(tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id,archived=False)
    q=q.filter(or_(ChatSession.id.startswith('LEGACY-'),ChatSession.id.in_(db.query(SessionTurn.session_id).filter(SessionTurn.tenant_id==user.tenant_id))))
    if cursor:
        try:time,id=cursor.split('|',1);time=datetime.fromisoformat(time)
        except ValueError:raise HTTPException(422,'Invalid chat-history cursor.')
        q=q.filter(or_(ChatSession.updated_at<time,and_(ChatSession.updated_at==time,ChatSession.id<id)))
    rows=q.order_by(ChatSession.updated_at.desc(),ChatSession.id.desc()).limit(51).all();result=[x for x in [data(db,user,s) for s in rows] if not (x['legacy'] and x['turn_count']==0)];db.commit()
    return {'sessions':sorted(result[:50],key=lambda x:(x['updated_at'],x['id']),reverse=True),'next_cursor':stamp(rows[49].updated_at)+'|'+rows[49].id if len(rows)>50 else None}

@router.get('/chat/{pid}/memory',response_model=RMChatMemory)
def memory(pid:str,exclude:str='',db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.assistant.memory import chat_memory
    p=party_for(db,user,pid,customer=True)
    if user.role!='CUSTOMER':raise HTTPException(403,'Earlier chats are visible only in the customer’s own account.')
    return chat_memory(db,user,p.id,exclude_session_id=exclude or None)

@router.post('/chat/{pid}/sessions',response_model=RMChatSession)
def create(pid:str,req:RMNewSession,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,pid,customer=True)
    if not db.query(Conversation).filter_by(tenant_id=user.tenant_id,party_id=pid,actor_id=user.user_id).first():
        from .rm import chat_history
        chat_history(pid,db,user)
    old=db.query(ChatSession).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,request_key=req.request_key).first()
    if old:
        if old.party_id!=pid:raise HTTPException(409,'Session request key belongs to another subject.')
        return data(db,user,old)
    recent=db.query(ChatSession).filter(ChatSession.tenant_id==user.tenant_id,ChatSession.actor_id==user.user_id,ChatSession.created_at>utc_now()-__import__('datetime').timedelta(minutes=1)).count()
    if recent>=15:raise HTTPException(429,'Please wait before opening more new chats.')
    s=ChatSession(id=uid('CHAT'),tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id,request_key=req.request_key);db.add(s);db.commit();return data(db,user,s)

@router.get('/chat/{pid}/sessions/{id}',response_model=RMConversation)
def history(pid:str,id:str,before:str='',db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    s,p=session_for(db,user,pid,id);q=turns_query(db,user,s)
    if before:
        pivot=db.query(Turn).filter_by(id=before,tenant_id=user.tenant_id,party_id=p.id,actor_id=user.user_id).first()
        if not pivot or not q.filter(Turn.id==pivot.id).first():raise HTTPException(404,'Message cursor is outside this session.')
        q=q.filter(or_(Turn.created_at<pivot.created_at,and_(Turn.created_at==pivot.created_at,Turn.id<pivot.id)))
    expired=q.filter(Turn.status=='PENDING',Turn.created_at<utc_now()-__import__('datetime').timedelta(seconds=60)).all()
    for turn in expired:turn.status='FAILED';turn.error_code='INTERRUPTED_REQUEST';turn.answer='This answer was interrupted. Check the original chat status before sending again.'
    if expired:db.commit()
    turns=q.order_by(Turn.created_at.desc(),Turn.id.desc()).limit(41).all();provider,ready=provider_info();info=data(db,user,s)
    return {'id':s.id,'party':party_data(db,p),'institution_name':user.institution_name,'version':info['version'],'turns':[turn_data(db,t) for t in reversed(turns[:40])],'provider':provider,'provider_ready':ready,'older_cursor':turns[39].id if len(turns)>40 else None}

@router.get('/quality/sessions',response_model=dict)
def monitored_sessions(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    from ..services.rm import quality_grant
    grant=quality_grant(db,user);scope=json.loads(grant.party_scope_json)
    query=db.query(ChatSession).filter_by(tenant_id=user.tenant_id)
    if scope:query=query.filter(ChatSession.party_id.in_(scope))
    rows=query.order_by(ChatSession.updated_at.desc(),ChatSession.id.desc()).limit(100).all()
    non_legacy=[s.id for s in rows if not s.id.startswith('LEGACY-')];counts={}
    if non_legacy:
        for sid_val,t_cnt,f_cnt in db.query(SessionTurn.session_id,func.count(Turn.id),func.sum(case((Turn.status=='FAILED',1),else_=0))).join(Turn,Turn.id==SessionTurn.id).filter(SessionTurn.tenant_id==user.tenant_id,SessionTurn.session_id.in_(non_legacy)).group_by(SessionTurn.session_id).all():counts[sid_val]=(int(t_cnt or 0),int(f_cnt or 0))
    result=[]
    for s in rows:
        if s.id.startswith('LEGACY-'):
            turns=turns_query(db,type('Actor',(),{'tenant_id':user.tenant_id,'user_id':s.actor_id})(),s);t_cnt=turns.count();f_cnt=turns.filter(Turn.status=='FAILED').count()
        else:t_cnt,f_cnt=counts.get(s.id,(0,0))
        if t_cnt>0:result.append({'id':s.id,'title':s.title if grant.content else 'Customer conversation','created_at':stamp(s.created_at),'updated_at':stamp(s.updated_at),'turns':t_cnt,'failures':f_cnt,'content_access':grant.content})
    return {'sessions':result,'method':'Latest 100 explicitly scoped session metadata records. Titles remain hidden without content authority; customer content stays in separately granted traces.'}
