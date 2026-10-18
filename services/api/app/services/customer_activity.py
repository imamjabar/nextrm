"""Institution-controlled, bounded relationship capture; no in-app RM messaging."""
import os,json,re,hashlib
from datetime import timedelta
from urllib.parse import quote
from sqlalchemy import or_
from fastapi import HTTPException
from ..models.entities import utc_now,UserAssignmentModel
from ..models.relationships import AppActivity,Source,Signal,Party
from .rm import uid,j,hash_payload,stamp,signal_data,contact_preferences_for_signals

PRODUCTS={'DEPOSIT':'Time deposit','LOAN':'Loan','SAVINGS':'Savings','NONE':'RM contact'}

def capture_policy(user):
    raw=os.environ.get('NEXTRM_CAPTURE_POLICY_JSON')
    if raw:
        try:
            policy=json.loads(raw).get(user.tenant_id,{})
            if not isinstance(policy,dict) or not isinstance(policy.get('enabled',False),bool):raise ValueError()
            channels=policy.get('channels',[])
            if not isinstance(channels,list) or any(x not in {'CHAT','APP_ACTIVITY','FINANCIAL_INSIGHT'} for x in channels):raise ValueError()
            return {'enabled':policy.get('enabled',False),'channels':channels,'version':str(policy.get('version','institution-v1'))}
        except (ValueError,TypeError,AttributeError):raise HTTPException(503,'Institution signal-capture configuration is invalid.')
    demo=user.data_mode=='SYNTHETIC' and os.getenv('ENVIRONMENT','development') in {'test','development'} and os.getenv('AUTH_PROVIDER','synthetic_demo')=='synthetic_demo'
    return {'enabled':demo,'channels':['CHAT','APP_ACTIVITY','FINANCIAL_INSIGHT'] if demo else [],'version':'local-mvp-capture-v1' if demo else 'NOT_CONFIGURED'}

def may_capture(user,channel):
    policy=capture_policy(user)
    return policy['enabled'] and channel in policy['channels']

def chat_capture(user,requested,message):
    # Explicit older private-turn contracts remain valid. The simplified UI omits this field.
    private=any(x in message.casefold() for x in ['keep this private','do not share with my rm',"don't share with my rm",'jangan bagikan'])
    return False if private or requested is False else True if requested is True else may_capture(user,'CHAT')

def rm_contact(db,user,party):
    from .coverage import coverage_for
    coverage=coverage_for(db,party)
    if coverage and coverage.mode!='DEDICATED':
        try:
            entries=json.loads(os.environ.get('NEXTRM_RM_CONTACTS_JSON','{}'));data=entries.get(user.tenant_id,{}).get('POOL:shared-service',{})
            if not isinstance(data,dict):raise ValueError()
            email=data.get('email');phone=data.get('phone')
            if email and (not isinstance(email,str) or not re.fullmatch(r'[A-Za-z0-9.!+_-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+',email) or email.endswith('.invalid')):raise ValueError()
            if phone and (not isinstance(phone,str) or not re.fullmatch(r'\+[1-9][0-9]{7,14}',phone)):raise ValueError()
        except (ValueError,TypeError,AttributeError):raise HTTPException(503,'Institution shared-team contact configuration is invalid; no fallback address is invented.')
        return {'name':'Relationship service team','email':email,'phone':phone,'email_href':'mailto:'+quote(email,safe='@.+-') if email else None,'phone_href':'tel:'+phone if phone else None,'status':'CONFIGURED' if email or phone else 'NOT_CONFIGURED','mode':'SHARED_TEAM'}
    member=db.query(UserAssignmentModel).filter_by(user_id=party.owner_id,tenant_id=user.tenant_id,role='RM',active=True).first()
    if not member:raise HTTPException(409,'Assigned RM directory needs review.')
    try:
        entries=json.loads(os.environ.get('NEXTRM_RM_CONTACTS_JSON','{}'))
        data=entries.get(user.tenant_id,{}).get(member.user_id,{})
        if not isinstance(data,dict):raise ValueError()
        email=data.get('email');phone=data.get('phone')
        if email and (not isinstance(email,str) or not re.fullmatch(r'[A-Za-z0-9.!+_-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+',email) or email.endswith('.invalid')):raise ValueError()
        if phone and (not isinstance(phone,str) or not re.fullmatch(r'\+[1-9][0-9]{7,14}',phone)):raise ValueError()
    except (ValueError,TypeError,AttributeError):raise HTTPException(503,'Institution RM contact configuration is invalid; no fallback address is invented.')
    return {'name':member.name,'email':email,'phone':phone,'email_href':'mailto:'+quote(email,safe='@.+-') if email else None,'phone_href':'tel:'+phone if phone else None,'status':'CONFIGURED' if email or phone else 'NOT_CONFIGURED','mode':'INSTITUTION_CONFIGURED' if email or phone else 'UNAVAILABLE'}

def record_activity(db,user,party,kind,product,key,origin='CUSTOMER_APP',occurred=None,mode=None):
    if kind not in {'PRODUCT_VIEW','RM_CONTACT_VIEW','APPLICATION_FAILED'} or product not in PRODUCTS:raise HTTPException(422,'Unsupported activity type or product.')
    if kind=='RM_CONTACT_VIEW' and product!='NONE' or kind!='RM_CONTACT_VIEW' and product=='NONE':raise HTTPException(422,'Choose the applicable product.')
    # Serialize event aggregation without changing the party revision or any financial state.
    db.query(Party).filter_by(id=party.id,tenant_id=user.tenant_id).with_for_update().one()
    db.refresh(party)
    payload=hash_payload({'kind':kind,'product':product,'origin':origin,'occurred':stamp(occurred) if occurred else None})
    old=db.query(AppActivity).filter_by(tenant_id=user.tenant_id,party_id=party.id,request_key=key).first()
    if old:
        if old.payload_hash!=payload:raise HTTPException(409,'Activity key conflicts with its original event.')
        return old
    now=utc_now();event_at=occurred or now
    if not -300<=(now-event_at).total_seconds()<=30*86400:raise HTTPException(422,'Activity time must be current and within the supported source window.')
    policy=may_capture(user,'APP_ACTIVITY')
    if not policy:raise HTTPException(403,'App activity capture is not enabled by this institution.')
    mode=mode or ('SIMULATED' if user.data_mode=='SYNTHETIC' else 'OBSERVED')
    source=Source(id=uid('APP-SRC'),tenant_id=user.tenant_id,party_id=party.id,kind='SYNTHETIC_APP_EVENT' if mode=='SIMULATED' else 'CUSTOMER_APP_EVENT',title=PRODUCTS[product]+' · '+kind.lower().replace('_',' '),content=j({'event':kind,'product':product,'origin':origin,'occurred_at':stamp(event_at),'mode':mode,'meaning':'Observed activity, not purchase intent, eligibility or a bank outcome.'}),mode=mode,event_at=event_at)
    source.content_hash=hashlib.sha256(source.content.encode()).hexdigest();db.add(source);db.flush()
    row=AppActivity(id=uid('APP-EVENT'),tenant_id=user.tenant_id,party_id=party.id,actor_id=user.user_id,kind=kind,product=product,origin=origin,occurred_at=event_at,request_key=key,payload_hash=payload,mode=mode,source_id=source.id)
    db.add(row);db.flush()
    if policy:
        from .governance import settings
        policy_settings=settings(db,user.tenant_id);start=now-timedelta(days=policy_settings['behavior_window_days'])
        records=db.query(AppActivity).filter_by(tenant_id=user.tenant_id,party_id=party.id,kind=kind,product=product).filter(AppActivity.occurred_at>=start,AppActivity.occurred_at<=now+timedelta(minutes=5)).all()
        count=len(records)
        service=kind=='APPLICATION_FAILED'
        capture=service or kind=='PRODUCT_VIEW' and count>=policy_settings['repeat_view_threshold'] and party.contact=='ALLOWED' and party.identity=='CONFIRMED'
        if capture:
            semantic='APP-'+kind+'-'+product
            signal=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=party.id).filter(or_(Signal.semantic_key==semantic,Signal.semantic_key.startswith(semantic+'-'))).order_by(Signal.updated_at.desc()).first()
            if not signal or signal.workflow in {'COMPLETED','DISMISSED','IN_PROGRESS'}:
                # An active task's reviewed source is immutable. Later observations remain in behavior history.
                if signal and signal.workflow=='IN_PROGRESS':
                    row.signal_id=signal.id;return row
                if signal:semantic+='-'+row.id[-8:]
                signal=Signal(id=uid('SIG'),tenant_id=user.tenant_id,party_id=party.id,source_id=source.id,owner_id=__import__('app.services.coverage',fromlist=['routing_owner']).routing_owner(db,party,escalate=service),semantic_key=semantic,category='SERVICE_ISSUE' if service else 'RESEARCH',urgency='TIME_SENSITIVE' if service else 'ROUTINE',evidence='OBSERVED',title=PRODUCTS[product]+(' opening encountered an error' if service else ' explored repeatedly'),need='',rationale='',uncertainty='',confirmed=False);db.add(signal);db.flush()
            if signal.review=='PROPOSED':
                evidence={'kind':kind,'product':product,'count':count,'threshold':policy_settings['repeat_view_threshold'],'window_days':policy_settings['behavior_window_days'],'governance_release':__import__('app.services.governance',fromlist=['released']).released(db,user.tenant_id)[1],'window_start':stamp(start),'window_end':stamp(now),'event_refs':[{'id':x.id,'source_id':x.source_id,'at':stamp(x.occurred_at),'mode':x.mode} for x in records]}
                summary=Source(id=uid('APP-SUMMARY'),tenant_id=user.tenant_id,party_id=party.id,kind='SYNTHETIC_APP_SUMMARY' if mode=='SIMULATED' else 'AUTHORIZED_APP_SUMMARY',title='App behavior evidence · '+PRODUCTS[product],content=j(evidence),content_hash=hash_payload(evidence),mode=mode);db.add(summary);db.flush()
                signal.source_id=summary.id;signal.need=(PRODUCTS[product]+' opening reported an error. Ask what assistance is needed; no rejection or credit decision is established.' if service else str(count)+' '+PRODUCTS[product].lower()+' detail views observed in a rolling '+str(policy_settings['behavior_window_days'])+'-day window. Ask whether information or help is needed; interest remains unconfirmed.')
                signal.rationale='APP-SIGNAL-1: institution-configured capture, exact observed event count/window and source references. Configured repetition prompts research review, never a hot lead.'
                signal.uncertainty='Behavior is observed, not confirmed intent. Application error is service friction, not loan rejection or failed eligibility.';signal.version=(signal.version or 0)+1;signal.updated_at=now
            db.flush();row.signal_id=signal.id
    return row

def behavior(db,user,party):
    from .governance import settings
    days=settings(db,user.tenant_id)['behavior_window_days']
    rows=db.query(AppActivity).filter_by(tenant_id=user.tenant_id,party_id=party.id).filter(AppActivity.occurred_at>=utc_now()-timedelta(days=days)).order_by(AppActivity.occurred_at.desc()).all();groups={}
    for x in rows:groups.setdefault((x.kind,x.product,x.mode),[]).append(x)
    events=[{'kind':kind,'product':product,'count':len(items),'window':'Rolling '+str(days)+' days','latest_at':stamp(items[0].occurred_at),'mode':mode,'interpretation':'Service friction; outcome and cause unconfirmed.' if kind=='APPLICATION_FAILED' else 'Observed exploration; not purchase intent or signing authority.' if kind=='PRODUCT_VIEW' else 'Contact details viewed; no call or email sent.'} for (kind,product,mode),items in groups.items()]
    signals=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=party.id,owner_id=user.user_id).filter(Signal.semantic_key.startswith('APP-')).all()
    prefs=contact_preferences_for_signals(db,user.tenant_id,[x.id for x in signals])
    return {'events':events,'signals':[signal_data(db,x,pref=prefs.get(x.id)) for x in signals],'method':'APP-SIGNAL-1: exact permitted event counts within the released time window. Repeated views produce research; opening errors produce service review. No inferred anxiety, propensity or purchase confirmation.'}


def seed_customer_activity(db):
    from ..core.security import CurrentUser
    from .rm_seed import sid
    from ..models.relationships import EngagementProfile
    from .enrichment import insights_for
    for user_id,key in [('usr-dina','DINA'),('usr-aditya','ADITYA'),('usr-nabila','NABILA')]:
        p=db.get(Party,sid('demo-bank',key))
        if not p:continue
        user=CurrentUser(user_id=user_id,name=p.name,email=f'{key.lower()}@example.invalid',role='CUSTOMER',tenant_id=p.tenant_id,institution_type='BANK',entity_id=p.id,data_mode='SYNTHETIC')
        if not may_capture(user,'APP_ACTIVITY'):continue
        if key=='DINA':
            for number in range(1,21):
                k='mvp-synthetic-deposit-view-'+str(number)
                if not db.query(AppActivity).filter_by(tenant_id=p.tenant_id,party_id=p.id,request_key=k).first():
                    record_activity(db,user,p,'PRODUCT_VIEW','DEPOSIT',k,origin='SYNTHETIC_BANK_APP',occurred=utc_now()-timedelta(minutes=30-number),mode='SIMULATED')
            k='mvp-synthetic-loan-opening-error'
            if not db.query(AppActivity).filter_by(tenant_id=p.tenant_id,party_id=p.id,request_key=k).first():
                record_activity(db,user,p,'APPLICATION_FAILED','LOAN',k,origin='SYNTHETIC_BANK_EVENT_ADAPTER',occurred=utc_now()-timedelta(minutes=8),mode='SIMULATED')
        elif key=='ADITYA':
            for n in range(1,7):
                k=f'mvp-synthetic-aditya-deposit-view-{n}'
                if not db.query(AppActivity).filter_by(tenant_id=p.tenant_id,party_id=p.id,request_key=k).first():
                    record_activity(db,user,p,'PRODUCT_VIEW','DEPOSIT',k,origin='SYNTHETIC_BANK_APP',occurred=utc_now()-timedelta(hours=40-6*n),mode='SIMULATED')
            k='mvp-synthetic-aditya-contact-view'
            if not db.query(AppActivity).filter_by(tenant_id=p.tenant_id,party_id=p.id,request_key=k).first():
                record_activity(db,user,p,'RM_CONTACT_VIEW','NONE',k,origin='SYNTHETIC_BANK_APP',occurred=utc_now()-timedelta(minutes=90),mode='SIMULATED')
        elif key=='NABILA':
            for n,hours in [(1,26),(2,3)]:
                k=f'mvp-synthetic-nabila-savings-view-{n}'
                if not db.query(AppActivity).filter_by(tenant_id=p.tenant_id,party_id=p.id,request_key=k).first():
                    record_activity(db,user,p,'PRODUCT_VIEW','SAVINGS',k,origin='SYNTHETIC_BANK_APP',occurred=utc_now()-timedelta(hours=hours),mode='SIMULATED')
        profile=db.query(EngagementProfile).filter_by(tenant_id=p.tenant_id,party_id=p.id).first()
        if profile:capture_financial_signals(db,user,p,insights_for(db,p,json.loads(profile.data_json)))
    from .demo_story import seed_demo_story
    seed_demo_story(db)

def capture_financial_signals(db,user,party,insights):
    from decimal import Decimal
    if not may_capture(user,'FINANCIAL_INSIGHT'):return
    from .governance import settings
    threshold=settings(db,user.tenant_id)['spending_change_percent']
    for item in insights:
        if not item.get('source') or item['status']=='UNAVAILABLE':continue
        gap=item['key']=='cash_flow' and item['status']=='GAP'
        spending=item['key']=='spending' and 'change_percent' in item['values'] and Decimal(item['values']['change_percent'])>=threshold
        if not gap and not spending:continue
        if party.contact!='ALLOWED' and not gap:continue
        key='FIN-'+item['key'];source=item['source']
        old=db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=party.id,semantic_key=key).first()
        if old:continue
        signal=Signal(id=uid('SIG'),tenant_id=user.tenant_id,party_id=party.id,source_id=source['id'],owner_id=__import__('app.services.coverage',fromlist=['routing_owner']).routing_owner(db,party,escalate=gap),semantic_key=key,category='GUIDANCE',urgency='TIME_SENSITIVE' if gap else 'ROUTINE',evidence='OBSERVED',title='Upcoming commitments need a cash-flow review' if gap else 'Spending changed across comparable periods',need=item['explanation'],rationale='FIN-SIGNAL-1: permitted fresh complete source, Decimal calculation. Gap is commitments above snapshot available funds; spending review uses the released comparison threshold. No propensity, credit risk or confirmed purchase intent.',uncertainty='Snapshot information requires current confirmation. Financial guidance is not a suitability or product decision.',confirmed=False)
        db.add(signal)
