import json
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..models.entities import utc_now
from ..models.relationships import Party,Source,Signal,Journey,Prospect,Turn,EngagementProfile
from ..schemas.rm import RMToday,RMPartySnapshot
from ..services.rm import require_rm,party_for,party_data,signal_data,journey_data,priority_key,stamp,need_order,contact_preferences_for_signals
from ..services.activity_feed import feed_for,chat_items
from ..services.assistant.engine import provider_info
router=APIRouter(prefix='/v1/rm',tags=['rm-today'])
JAKARTA=ZoneInfo('Asia/Jakarta')
READY_TIERS={'READY_FOR_DISCUSSION','REVIEW_FIRST','REVIEW'}

@router.get('/today',response_model=RMToday)
def today(db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user)
    from ..services.coverage import owned_ids
    from .rm import prospects_data
    parties=db.query(Party).filter(Party.tenant_id==user.tenant_id,Party.relationship=='EXISTING_CUSTOMER',Party.id.in_(owned_ids(db,user))).all()
    names={p.id:p.name for p in parties}
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).all()
    tasks_rows=db.query(Journey).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED'])).order_by(Journey.created_at.desc()).all()
    sig_ids=[s.id for s in signals]+[x.signal_id for x in tasks_rows if x.signal_id]
    prefs=contact_preferences_for_signals(db,user.tenant_id,sig_ids)
    rows=[signal_data(db,s,pref=prefs.get(s.id)) for s in signals];rows.sort(key=need_order);top=rows[:20]
    sources={s.id:s for s in db.query(Source).filter(Source.tenant_id==user.tenant_id,Source.id.in_([x['source_id'] for x in top])).all()} if top else {}
    queue=[{'signal':r,'quote':sources[r['source_id']].content if r['origin'] in {'CHAT','REQUEST'} and r['source_id'] in sources else None} for r in top]
    now=utc_now();due=lambda x:datetime.fromisoformat(x['due_at']) if x['due_at'] else None
    tasks=[journey_data(db,x,pref=prefs.get(x.signal_id)) for x in tasks_rows]
    overdue=[x for x in tasks if due(x) and due(x)<now]
    tasks.sort(key=lambda x:(not (due(x) and due(x)<now),due(x) is None,due(x) or now))
    ready=[x for x in prospects_data(db,db.query(Prospect).filter_by(tenant_id=user.tenant_id,owner_id=user.user_id).all()) if x['priority_tier'] in READY_TIERS]
    all_activity=feed_for(db,user,names,200);latest={}
    for item in all_activity:latest.setdefault(item['party_id'],item)
    midnight=datetime.now(JAKARTA).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    conversations=db.query(Turn).filter(Turn.tenant_id==user.tenant_id,Turn.party_id.in_(list(names)),Turn.share.is_(True),Turn.status=='COMPLETED',Turn.created_at>=midnight).count() if names else 0
    open_needs={}
    for s in signals:open_needs[s.party_id]=open_needs.get(s.party_id,0)+1
    customers=[{'party':party_data(db,p),'open_needs':open_needs.get(p.id,0),'last_activity_at':latest[p.id]['at'] if p.id in latest else None,'last_topic':latest[p.id]['topic'] if p.id in latest else None} for p in sorted(parties,key=lambda p:p.name)]
    customers.sort(key=lambda x:x['last_activity_at'] or '',reverse=True)
    provider,provider_ready=provider_info()
    counts={'customers':len(parties),'needs_open':len(signals),'needs_to_review':sum(x.review=='PROPOSED' for x in signals),'urgent_service':sum(x.category=='SERVICE_ISSUE' and x.urgency in {'URGENT','TIME_SENSITIVE'} for x in signals),'followups_open':len(tasks),'followups_overdue':len(overdue),'prospects_ready':len(ready),'conversations_today':conversations}
    return {'generated_at':stamp(now),'rm_name':user.name,'counts':counts,'queue':queue,'activity':all_activity[:12],'followups':tasks[:5],'prospects':ready[:4],'customers':customers,'provider':provider,'provider_ready':provider_ready,'method':'Counts and lists come from the same assigned records in one request. Chats appear only when the bank capture policy shares them; private turns never appear.'}

@router.get('/parties/{pid}/snapshot',response_model=RMPartySnapshot)
def snapshot(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);p=party_for(db,user,pid)
    method='Same core-banking calculation the customer sees on Home (FIN-PIPE-1). Read-only. Only chats shared by bank policy; private turns excluded.'
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':return {'party_id':p.id,'available':False,'insights':[],'conversations':[],'method':method}
    from ..services.enrichment import insights_for
    profile=db.query(EngagementProfile).filter_by(tenant_id=user.tenant_id,party_id=p.id).first()
    return {'party_id':p.id,'available':True,'insights':insights_for(db,p,json.loads(profile.data_json) if profile else {}),'conversations':chat_items(db,user.tenant_id,{p.id:p.name},20),'method':method}
