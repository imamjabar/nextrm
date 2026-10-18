"""Policy-shared customer chats and observed app events for assigned RM views; private turns never appear."""
import json
from datetime import timedelta
from ..models.entities import utc_now
from ..models.relationships import Turn,AppActivity
from .rm import stamp
from .customer_activity import PRODUCTS

TOPIC={'SAVINGS':'Savings','DEPOSIT':'Deposits','SERVICE':'Payments','CARD':'Cards','WEALTH':'Investments','MERCHANT':'Business','PRIVACY':'Privacy','CLARIFY':'General help','LOAN':'Loans'}
APP_TITLE={'PRODUCT_VIEW':lambda first,product:f"{first} viewed {product.lower()} details",'APPLICATION_FAILED':lambda first,product:f"{first}'s {product.lower()} opening reported an error",'RM_CONTACT_VIEW':lambda first,product:f"{first} opened your contact details"}

def chat_items(db,tenant_id,names:dict[str,str],limit:int):
    if not names:return []
    rows=db.query(Turn).filter(Turn.tenant_id==tenant_id,Turn.party_id.in_(list(names)),Turn.share.is_(True),Turn.status=='COMPLETED').order_by(Turn.created_at.desc()).limit(limit).all()
    result=[]
    for t in rows:
        topic=TOPIC.get(t.route,'General help');first=names[t.party_id].split()[0]
        result.append({'id':'chat:'+t.id,'kind':'CHAT','party_id':t.party_id,'name':names[t.party_id],'at':stamp(t.created_at),'title':f"{first} asked about {topic.lower()}",'text':t.message,'topic':topic,'signal_id':json.loads(t.output_json or '{}').get('signal_id'),'mode':t.mode})
    return result

def app_items(db,tenant_id,names:dict[str,str],days:int):
    if not names:return []
    rows=db.query(AppActivity).filter(AppActivity.tenant_id==tenant_id,AppActivity.party_id.in_(list(names)),AppActivity.occurred_at>=utc_now()-timedelta(days=days)).order_by(AppActivity.occurred_at.asc()).all()
    groups={}
    for a in rows:
        g=groups.setdefault((a.party_id,a.kind,a.product),{'count':0,'at':a.occurred_at,'signal_id':None,'mode':a.mode})
        g['count']+=1;g['at']=a.occurred_at;g['mode']=a.mode
        if a.signal_id:g['signal_id']=a.signal_id
    result=[]
    for (pid,kind,product),g in groups.items():
        if kind not in APP_TITLE:continue
        label=PRODUCTS.get(product,product.title());count=g['count']
        result.append({'id':'app:'+pid+':'+kind+':'+product,'kind':'APP','party_id':pid,'name':names[pid],'at':stamp(g['at']),'title':APP_TITLE[kind](names[pid].split()[0],label),'text':f"{count} {'time' if count==1 else 'times'} in the last {days} days",'topic':label,'signal_id':g['signal_id'],'mode':g['mode']})
    return result

def feed_for(db,user,names:dict[str,str],limit:int):
    from .governance import settings
    days=int(settings(db,user.tenant_id)['behavior_window_days'])
    return sorted(chat_items(db,user.tenant_id,names,limit)+app_items(db,user.tenant_id,names,days),key=lambda x:x['at'],reverse=True)[:limit]
