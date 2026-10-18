"""Bounded engagement decisions. Sources are data, never executable instructions."""
import json,hashlib
from datetime import datetime,timedelta,timezone,date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from ..models.entities import utc_now
from ..models.relationships import (Party,Source,Nudge,Signal,Prospect,Journey,ReviewEvent,
    EngagementProfile,SuggestionMeta,EngagementDecision,EngagementFeedback,ContactRecord)
from .rm import j,uid,stamp,hash_payload,source_data,priority_key,prospect_priority
METHOD='ENGAGE-1: permission and freshness gates, care before requested guidance, recognition and promotion; no propensity score.'
FAMILIES={
'E01':('welcome','EDUCATION','HELP','Welcome to your personal banking space','Explore how your assistant can help with banking questions and human help.','What can my banking assistant help me with?','help'),
'E02':('recognition','RECOGNITION','HELP','A moment worth celebrating','Wishing you a wonderful birthday. There is nothing you need to buy or do.','Thank you. What banking help is available?','help'),
'E03':('goals','GUIDANCE','SAVINGS','Make room for what matters','Review your declared goal, timing and the money you need to keep accessible.','Help me think through my declared savings goal.','savings'),
'E04':('product_help','EDUCATION','SERVICE','Get more clarity on your existing product','Understand your existing savings account before considering anything new.','How does an everyday savings account work?','savings'),
'E05':('service','CARE','SERVICE','Start with the issue that needs care','Your service request deserves attention. Ask for help preparing the next step; resolution is not confirmed here.','I would like RM help with my current banking service issue.','payments'),
'E06':('maturity','GUIDANCE','DEPOSIT','Your maturity discussion, prepared','Review the stated maturity date, liquidity needs and withdrawal conditions. No renewal instruction is made here.','What should I discuss with my RM before my deposit matures?','deposit'),
'E07':('liquidity','COMMERCIAL','DEPOSIT','Keep your options accessible','You asked about liquidity. Clarify reserves and timing before discussing savings or deposit options.','How should I think about liquidity before discussing a deposit?','deposit'),
'E08':('preferences','EDUCATION','HELP','Make suggestions work for you','You control interests, private exploration and commercial contact. Service help stays available.','How do my privacy and contact choices work?','privacy'),
'E09':('cash_flow','CARE','SERVICE','Review your upcoming commitments','Inspect the sourced cash-flow snapshot and ask for help if needed. Amounts are a snapshot, not a live balance.','Help me understand my upcoming commitments without making a payment.','savings'),
'E10':('spending','GUIDANCE','SAVINGS','Understand a change in spending','Review comparable periods and the source of this category change. A change is not a judgment about you.','How can I review changes in my spending?','savings'),
'E11':('travel','GUIDANCE','SERVICE','A checklist for your travel plan','Review payment access, current fees and security channels before you travel.','What should I check about payment access before travelling?','cards'),
'E12':('reconnect','COMMERCIAL','HELP','Is there anything we can help with?','The supplied activity snapshot shows a quieter period. It does not tell us why.','I would like help getting familiar with my banking services again.','help')}

def fresh(source,seconds=30*86400):
    return bool(source and -300<=(utc_now()-source.event_at.replace(tzinfo=timezone.utc)).total_seconds()<=seconds)

def scoped_source(db,tenant,pid,id,kind=None):
    s=db.query(Source).filter_by(id=id,tenant_id=tenant).first()
    return s if s and (s.party_id==pid or (s.party_id is None and s.kind=='APPROVED_KNOWLEDGE')) and (not kind or s.kind==kind) else None

def profile_for(db,p):
    row=db.query(EngagementProfile).filter_by(tenant_id=p.tenant_id,party_id=p.id).first()
    if not row:
        row=EngagementProfile(id=uid('PROFILE'),tenant_id=p.tenant_id,party_id=p.id,data_json=j({'goal':'','horizon':'','interests':[],'share_context':False,'snoozes':{},'facts':{}}))
        db.add(row);db.flush()
    return row

def profile_data(row,p):
    d=json.loads(row.data_json)
    return {'version':row.version,'goal':d.get('goal',''),'horizon':d.get('horizon',''),'interests':d.get('interests',[]),'share_context':d.get('share_context',False),'source_id':d.get('source_id'),'topic_snoozes':d.get('snoozes',{}),'commercial_allowed':p.contact=='ALLOWED'}

def make_source(db,p,title,content,kind='CUSTOMER_DECLARED_CONTEXT'):
    s=Source(id=uid('CONTEXT'),tenant_id=p.tenant_id,party_id=p.id,kind=kind,title=title,content=content,content_hash=hashlib.sha256(content.encode()).hexdigest(),mode='SIMULATED' if json.loads(p.context_json).get('mode')=='SYNTHETIC' else 'LIVE')
    db.add(s);db.flush();return s

def seed_enrichment(db):
    # Explicit synthetic event adapter; never called by application startup or reads.
    from .insights_pipeline import customer_for_party
    for p in db.query(Party).filter_by(kind='PERSON',relationship='EXISTING_CUSTOMER').all():
        if db.query(EngagementProfile).filter_by(tenant_id=p.tenant_id,party_id=p.id).first():continue
        ctx=json.loads(p.context_json);now=utc_now();facts={'timezone':'Asia/Jakarta','relationship_started':now.date().isoformat(),'birthday':'1991-10-03' if p.name=='Dina Rahma' else None,'maturity_date':ctx.get('maturity_date'),'products':ctx.get('products',[]),'liquidity_requested':p.name=='Aditya Pratama','travel_declared':False,'inactivity_days':None}
        event=make_source(db,p,'Synthetic permitted lifecycle snapshot',j(facts),'SYNTHETIC_LIFECYCLE')
        facts['source_id']=event.id
        d={'goal':ctx.get('declared_goal',''),'horizon':'','interests':['goals'],'share_context':True,'snoozes':{},'facts':facts}
        goal=make_source(db,p,'Synthetic customer-declared goal',d['goal'],'SYNTHETIC_CUSTOMER_CONTEXT');d['source_id']=goal.id
        cust=customer_for_party(db,p)
        if cust:
            from .insights_pipeline import features_for, refresh_bank_data_source
            d['financial_source_id']=refresh_bank_data_source(db,p,features_for(db,cust),now).id
        db.add(EngagementProfile(id=uid('PROFILE'),tenant_id=p.tenant_id,party_id=p.id,data_json=j(d)))
    db.flush()

def insights_for(db,p,d):
    """Insight cards come only from linked core-banking data (FIN-PIPE-1); unlinked parties get UNAVAILABLE cards."""
    from .insights_pipeline import customer_for_party, insight_cards, unavailable_cards
    if not customer_for_party(db,p):return unavailable_cards()
    cards=insight_cards(db,p)
    spend=next((c for c in cards if c['key']=='spending'),None)
    correction=db.query(EngagementFeedback).filter_by(tenant_id=p.tenant_id,party_id=p.id,action='CATEGORY_CORRECTION').order_by(EngagementFeedback.created_at.desc()).first()
    if spend and spend.get('source') and correction:
        corrected=json.loads(correction.result_json)
        if corrected.get('source_id')==spend['source']['id'] and corrected.get('source_version')==spend['source']['version'] and corrected.get('source_hash')==spend['source']['hash']:
            spend['explanation']+=' Customer-provided category correction: '+corrected['category']+'. Original attribution is retained.'
    return cards
def eligibility(db,row,p,profile=None,insights=None):
    meta=db.query(SuggestionMeta).filter_by(id=row.id,tenant_id=p.tenant_id).first()
    if not meta:return None
    now=utc_now();profile=profile or profile_for(db,p);d=json.loads(profile.data_json);deps=json.loads(meta.dependencies_json)
    if row.state in {'REQUESTED','DISMISSED'}:return 'Choice already recorded'
    if meta.expires_at.replace(tzinfo=timezone.utc)<=now:return 'Suggestion expired'
    if deps.get('goal_hash') and deps['goal_hash']!=hash_payload({'goal':d.get('goal'),'horizon':d.get('horizon'),'interests':d.get('interests')}):return 'Declared context changed'
    for id,version,digest in deps['sources']:
        src=scoped_source(db,p.tenant_id,p.id,id)
        if not src or src.version!=version or src.content_hash!=digest or hashlib.sha256(src.content.encode()).hexdigest()!=digest:return 'Source changed or binding unavailable'
        if not fresh(src,86400 if src.kind.endswith('SUMMARY') else 30*86400):return 'Source is stale or future-dated'
    snooze=d.get('snoozes',{}).get(meta.topic)
    if snooze and datetime.fromisoformat(snooze)>now:return 'Topic snoozed by customer'
    if meta.category=='COMMERCIAL':
        if p.contact!='ALLOWED' or p.identity!='CONFIRMED':return 'Commercial contact or identity restriction'
        urgent=db.query(Signal).filter_by(tenant_id=p.tenant_id,party_id=p.id,category='SERVICE_ISSUE').filter(Signal.urgency.in_(['URGENT','TIME_SENSITIVE']),Signal.workflow.notin_(['COMPLETED','DISMISSED'])).first()
        if urgent:return 'Service care takes priority'
        ins=insights if insights is not None else insights_for(db,p,d)
        if any(x['status']=='GAP' for x in ins):return 'Financial care takes priority'
    return ''

def candidate(db,p,profile,family,source,expires,goal=False,body=None,title=None,prompt=None,card=None):
    topic,category,route,default_title,default_body,default_prompt,kb=FAMILIES[family]
    knowledge=db.query(Source).filter(Source.tenant_id==p.tenant_id,Source.kind=='APPROVED_KNOWLEDGE',Source.id.endswith('KB-'+kb)).first()
    if not knowledge or not source:return None
    d=json.loads(profile.data_json);context=hash_payload({'goal':d.get('goal'),'horizon':d.get('horizon'),'interests':d.get('interests')}) if goal else None
    dependencies={'sources':[[s.id,s.version,s.content_hash] for s in [source,knowledge]],'goal_hash':context,'rule':'ENGAGE-1','content':'ENGAGE-COPY-1'}
    identity={'party':p.id,'family':family,'occasion':expires.date().isoformat()} if family in {'E01','E02','E06'} else {'party':p.id,'family':family,'dependencies':dependencies}
    id='ENR-'+hash_payload(identity)[:48];row=db.get(Nudge,id)
    if not row:
        meta_deps=dict(dependencies)
        if card:
            from .assistant.nudge_copy import phrase_nudge
            copy=phrase_nudge(card,knowledge.content)
            title,body,prompt=copy['title'],copy['body'],copy['prompt']
            meta_deps['copy']={'mode':copy['mode'],'model':copy['model'],'rejected':bool(copy.get('rejection_reason'))}
        row=Nudge(id=id,tenant_id=p.tenant_id,party_id=p.id,source_id=source.id,knowledge_id=knowledge.id,route=route,title=title or default_title,body=body or default_body,prompt=prompt or (default_prompt+((' Goal: '+d['goal']+'. Horizon: '+d.get('horizon','not specified')) if goal and d.get('goal') else '')))
        db.add(row);db.flush();db.add(SuggestionMeta(id=id,tenant_id=p.tenant_id,family=family,topic=topic,category=category,dependencies_json=j(meta_deps),expires_at=expires));db.flush()
    return row

def feed(db,p,user=None):
    from ..routers.engagement import nudge_data
    profile=profile_for(db,p);d=json.loads(profile.data_json);facts=d.get('facts',{});now=utc_now()
    event=scoped_source(db,p.tenant_id,p.id,facts.get('source_id'))
    if event and event.kind in {'SYNTHETIC_LIFECYCLE','AUTHORIZED_LIFECYCLE'} and hashlib.sha256(event.content.encode()).hexdigest()==event.content_hash:
        try:facts=json.loads(event.content)
        except (ValueError,TypeError):facts={}
        if not isinstance(facts,dict):facts={}
    else:facts={}
    try:local=now.astimezone(ZoneInfo(facts.get('timezone','Asia/Jakarta')))
    except (KeyError,ValueError,TypeError):local=now
    goal=scoped_source(db,p.tenant_id,p.id,d.get('source_id'))
    insights=insights_for(db,p,d);candidates=[]
    financial=scoped_source(db,p.tenant_id,p.id,d.get('financial_source_id'))
    if not financial and insights and insights[0].get('source'):
        financial=scoped_source(db,p.tenant_id,p.id,insights[0]['source']['id'])
    from .insights_pipeline import score_candidate
    candidate_scores={}
    candidate_whys={}
    def add(family,src,days=30,goal_bound=False,body=None,title=None,prompt=None,expires=None,score=None,why=None,card=None):
        row=candidate(db,p,profile,family,src,expires or now+timedelta(days=days),goal_bound,body,title,prompt,card)
        if row:
            candidates.append(row)
            meta=db.get(SuggestionMeta,row.id)
            candidate_scores[row.id]=score if score is not None else score_candidate(meta.category,Decimal('0.50'),0)
            if why:candidate_whys[row.id]=why
    if event and facts.get('relationship_started'):
        try:
            start=date.fromisoformat(facts['relationship_started'])
            if 0<=(local.date()-start).days<=7:add('E01',event,expires=datetime.combine(start+timedelta(days=8),datetime.min.time(),tzinfo=local.tzinfo).astimezone(timezone.utc))
        except ValueError:pass
    recognition=None
    if event and facts.get('birthday'):
        try:
            birthday=date.fromisoformat(facts['birthday'])
            if (birthday.month,birthday.day)==(local.month,local.day) and birthday<=local.date():recognition='Wishing you a wonderful birthday. There is nothing you need to buy or do.'
        except (ValueError,TypeError):pass
    if not recognition and event and facts.get('relationship_started'):
        try:
            started=date.fromisoformat(facts['relationship_started'])
            if (started.month,started.day)==(local.month,local.day) and local.year>started.year:recognition='Thank you for '+str(local.year-started.year)+' years with your institution. No product suggestion is attached.'
        except (ValueError,TypeError):pass
    if recognition:add('E02',event,body=recognition,expires=datetime.combine(local.date()+timedelta(days=1),datetime.min.time(),tzinfo=local.tzinfo).astimezone(timezone.utc))
    if goal and d.get('goal'):add('E03',goal,goal_bound=True,score=score_candidate('GUIDANCE',Decimal('0.80'),0))
    if event and 'Everyday savings' in facts.get('products',[]):add('E04',event)
    service=db.query(Signal).filter_by(tenant_id=p.tenant_id,party_id=p.id,category='SERVICE_ISSUE').filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).order_by(Signal.created_at.desc()).first()
    if service:add('E05',scoped_source(db,p.tenant_id,p.id,service.source_id),score=Decimal('150.00'),why='Urgent service issue reported.')
    td_card=next((x for x in insights if x['key']=='term_deposit' and x['status']=='AVAILABLE'),None)
    if td_card:
        bal_str=td_card['values'].get('balance','')
        mat_str=td_card['values'].get('maturity_date','')
        days_left=int(td_card['values'].get('days_to_maturity','30'))
        sc=score_candidate('GUIDANCE',Decimal('1.00')-(Decimal(days_left)/Decimal('30.00')),recency_days=days_left)
        why_text=f"Term deposit of {bal_str} IDR matures on {mat_str} ({days_left} days remaining)."
        body='The supplied maturity date is '+mat_str+'. Review timing and withdrawal terms with your RM; no renewal is performed.'
        add('E06',financial or event,body=body,expires=datetime.combine(date.fromisoformat(mat_str)+timedelta(days=1),datetime.min.time(),tzinfo=local.tzinfo).astimezone(timezone.utc),score=sc,why=why_text,card=td_card)
    elif event and facts.get('maturity_date'):
        try:
            maturity=date.fromisoformat(facts['maturity_date'])
            if 0<=(maturity-local.date()).days<=30:
                sc=score_candidate('GUIDANCE',Decimal('0.50'),recency_days=(maturity-local.date()).days)
                add('E06',event,body='The supplied maturity date is '+maturity.isoformat()+'. Review timing and withdrawal terms with your RM; no renewal is performed.',expires=datetime.combine(maturity+timedelta(days=1),datetime.min.time(),tzinfo=local.tzinfo).astimezone(timezone.utc),score=sc)
        except ValueError:pass
    idle_card=next((x for x in insights if x['key']=='idle_cash' and x['status']=='AVAILABLE'),None)
    if idle_card:
        idle_amt=Decimal(idle_card['values'].get('idle_cash','0.00'))
        mag=min(Decimal('1.00'),max(Decimal('0.20'),idle_amt/Decimal('50000000.00')))
        sc=score_candidate('COMMERCIAL',mag,recency_days=5)
        why_text=f"Savings balance of {idle_card['values'].get('savings_balance','')} IDR exceeds reserve threshold by {idle_card['values'].get('idle_cash','')} IDR."
        add('E07',financial or event,score=sc,why=why_text,card=idle_card)
    elif event and facts.get('liquidity_requested') is True:
        sc=score_candidate('COMMERCIAL',Decimal('0.50'),recency_days=0)
        add('E07',event,score=sc)
    # Preference help needs no inferred customer event.
    privacy=db.query(Source).filter(Source.tenant_id==p.tenant_id,Source.kind=='APPROVED_KNOWLEDGE',Source.id.endswith('KB-privacy')).first()
    add('E08',privacy)
    if financial and insights[0]['status']!='UNAVAILABLE':
        is_gap=insights[0]['status']=='GAP'
        diff_val=Decimal(insights[0]['values'].get('difference','0.00')) if 'difference' in insights[0]['values'] else Decimal('0.00')
        mag=min(Decimal('1.00'),max(Decimal('0.20'),abs(diff_val)/Decimal('5000000.00'))) if is_gap else Decimal('0.40')
        sc=score_candidate('CARE',mag,recency_days=0,is_urgent_care=is_gap)
        why_text=f"Available funds {insights[0]['values'].get('available','')} IDR vs upcoming commitments {insights[0]['values'].get('commitments','')} IDR (difference: {insights[0]['values'].get('difference','')} IDR)."
        add('E09',financial,days=1,score=sc,why=why_text,card=insights[0])
    if financial and insights[1]['status']=='AVAILABLE':
        pct_val=Decimal(insights[1]['values'].get('change_percent','20.00')) if 'change_percent' in insights[1]['values'] else Decimal('20.00')
        mag=min(Decimal('1.00'),max(Decimal('0.20'),abs(pct_val)/Decimal('100.00')))
        sc=score_candidate('GUIDANCE',mag,recency_days=1)
        why_text=f"{insights[1].get('title','Category')} changed by {insights[1]['values'].get('change','')} IDR ({insights[1]['values'].get('change_percent','0')}%)."
        add('E10',financial,days=1,score=sc,why=why_text,card=insights[1])
    if goal and ('travel' in d.get('interests',[]) or 'travel' in d.get('goal','').lower()):add('E11',goal,goal_bound=True)
    if event and isinstance(facts.get('inactivity_days'),int) and facts['inactivity_days']>=90:add('E12',event,days=7)
    decisions=[];eligible=[]
    for row in candidates:
        reason=eligibility(db,row,p,profile,insights=insights);meta=db.get(SuggestionMeta,row.id)
        decisions.append({'nudge_id':row.id,'family':meta.family,'category':meta.category,'source_versions':json.loads(meta.dependencies_json)['sources'],'expires_at':stamp(meta.expires_at),'result':'EXCLUDED' if reason else 'ELIGIBLE','reason':reason or 'Current sourced context and permitted useful action'})
        if not reason:eligible.append(row)
    # Existing seeds remain accessible through their original endpoints, but do not duplicate the feed.
    order={'CARE':0,'GUIDANCE':1,'EDUCATION':2,'RECOGNITION':3,'COMMERCIAL':4}
    eligible.sort(key=lambda row:(order[db.get(SuggestionMeta,row.id).category],-candidate_scores.get(row.id,Decimal('0.00')),row.id))
    from .governance import settings
    policy=settings(db,p.tenant_id)
    eligible=[row for row in eligible if db.get(SuggestionMeta,row.id).family in policy['enabled_families']]
    for item in decisions:
        if item['family'] not in policy['enabled_families']:item['result']='EXCLUDED';item['reason']='Nudge family disabled by institution governance'
    selected=eligible[:policy['max_nudges']]
    recognition=next((r for r in eligible if db.get(SuggestionMeta,r.id).category=='RECOGNITION'),None)
    if recognition and recognition not in selected and policy['max_nudges']>=2:
        selected=selected[:max(0,policy['max_nudges']-1)]+[recognition]
    for item in decisions:
        if item['result']=='ELIGIBLE':item['result']='SELECTED' if item['nudge_id'] in {r.id for r in selected} else 'DEFERRED';item['reason']='Selected by care-first order' if item['result']=='SELECTED' else 'Feed budget: one primary and two optional items'
    payload={'governance_release':__import__('app.services.governance',fromlist=['released']).released(db,p.tenant_id)[1],'method':METHOD,'rule_version':'ENGAGE-1','content_version':'ENGAGE-COPY-1','profile_version':profile.version,'party_version':p.version,'items':decisions}
    digest=hash_payload(payload);decision=db.query(EngagementDecision).filter_by(tenant_id=p.tenant_id,party_id=p.id,digest=digest).first()
    if not decision:
        decision=EngagementDecision(id=uid('DECISION'),tenant_id=p.tenant_id,party_id=p.id,digest=digest,data_json=j(payload));db.add(decision);db.flush()
    result=[]
    for index,row in enumerate(selected):
        meta=db.get(SuggestionMeta,row.id)
        why_text=candidate_whys.get(row.id,f"Based on the linked {meta.category.lower()} evidence. Explore is private; an explicit shared help request is a separate choice.")
        result.append({**nudge_data(db,row),'family':meta.family,'topic':meta.topic,'category':meta.category,'expires_at':stamp(meta.expires_at),'primary':index==0,'can_request_rm':meta.category!='RECOGNITION' and (row.route=='SERVICE' or p.contact=='ALLOWED'),'why':why_text})
    comparisons=[]
    for key,title,product in [('savings','Accessible everyday savings','Everyday savings'),('deposit','Term deposit discussion','Term deposit')]:
        src=db.query(Source).filter(Source.tenant_id==p.tenant_id,Source.kind=='APPROVED_KNOWLEDGE',Source.id.endswith('KB-'+key)).first()
        if src and fresh(src):comparisons.append({'title':title,'education':src.content,'ownership':'Already held' if product in json.loads(p.context_json).get('products',[]) else 'Not shown in available product context','eligibility':'Not assessed; discussion is not approval','terms_status':'Live fees and rates unavailable','source':source_data(src)})
    db.commit()
    return {'profile':profile_data(profile,p),'nudges':result,'decisions':decisions,'decision_id':decision.id,'method':METHOD,'insights':insights,'comparisons':comparisons}
