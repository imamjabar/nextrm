import hashlib
from datetime import timedelta,timezone
from ..models.entities import utc_now
from ..models.relationships import Party,Conversation,ChatSession,SessionTurn,Source,Turn,Signal,Journey,Prospect
from .rm import hash_payload,j
from .rm_seed import sid
from .assistant.engine import LOCAL_MODEL,PROMPT_VERSION,ROUTE_KB

SPECS=[
    ('DINA-1','Saving for school fees',timedelta(hours=26),'SAVINGS',
     "Can I talk to my RM about saving for my children's school fees next July?",
     "I have shared your request with your relationship manager, Maya Putri. She will contact you through the bank's official channels. Meanwhile, keeping school money in a separate savings pocket makes progress toward your education goal easier to see.",
     ('GUIDANCE','ROUTINE','Savings conversation',"Customer asked to discuss saving for her children's school fees next July.")),
    ('DINA-2','Spending this month',timedelta(minutes=50),'SAVINGS',
     'Why did my spending go up this month?',
     'Your Home tab compares spending by category for the last 30 days with the previous period. Open Spending on Home to see which category grew the most.',
     None),
    ('ADITYA-1','Term deposit maturity',timedelta(hours=3),'DEPOSIT',
     'My term deposit matures on 30 October. Can my RM call me about my options?',
     'I have passed your request to your relationship manager, Maya Putri. She will contact you through the bank\'s official channels before the deposit matures. Before that call, think about how much you want to keep easy to access.',
     ('GUIDANCE','TIME_SENSITIVE','Deposit / liquidity conversation','Customer asked for an RM call about options before his term deposit matures on 30 October.')),
    ('ADITYA-2','Portfolio check',timedelta(minutes=35),'WEALTH',
     'How did my investments do in the last 30 days?',
     'Open Investments on Home to see your portfolio value and its 30-day change, calculated from your holdings. Ask me about a specific fund or stock and I can explain what moved.',
     None),
    ('NABILA-1','Card delivery',timedelta(hours=5),'CARD',
     'My debit card still has not arrived after two weeks. Can you help?',
     'I am sorry about the wait. I have flagged this for your relationship manager, Maya Putri, so the delivery can be checked. If you think the card may be lost, contact your bank\'s official support line to block it.',
     ('SERVICE_ISSUE','TIME_SENSITIVE','Card service needs attention','Customer reports her debit card has not arrived after two weeks.')),
    ('NABILA-2','Laptop goal',timedelta(minutes=20),'SAVINGS',
     'Am I on track to buy my work laptop?',
     'Your Goals tile on Home shows progress toward your laptop goal from your recorded savings. Because your income varies, setting aside a fixed share of each project payment keeps progress steady.',
     None),
]

def seed_demo_story(db,tenant='demo-bank'):
    now=utc_now()
    for key,title,delta,route,message,answer,need_spec in SPECS:
        persona,n=key.split('-');actor_id='usr-'+persona.lower();pid=sid(tenant,persona);party=db.get(Party,pid)
        if not party:continue
        t_time=now-delta;conv_id=sid(tenant,'CONV-'+persona)
        conv=db.query(Conversation).filter_by(tenant_id=tenant,party_id=party.id,actor_id=actor_id).first()
        if not conv:
            conv=Conversation(id=conv_id,tenant_id=tenant,party_id=party.id,actor_id=actor_id,version=1,created_at=t_time)
            db.add(conv);db.flush()
        chat_id=sid(tenant,'CHAT-'+key);session=db.get(ChatSession,chat_id)
        if not session:
            session=ChatSession(id=chat_id,tenant_id=tenant,party_id=party.id,actor_id=actor_id,title=title,version=1,request_key='seed-chat-'+key,archived=False,created_at=t_time,updated_at=t_time)
            db.add(session);db.flush()
        source_id=sid(tenant,'MSG-'+key);source=db.get(Source,source_id)
        if not source:
            source=Source(id=source_id,tenant_id=tenant,party_id=party.id,kind='CUSTOMER_MESSAGE',title='Customer conversation · '+party.name,content=message,content_hash=hashlib.sha256(message.encode()).hexdigest(),mode='SIMULATED',version=1,event_at=t_time,ingested_at=t_time)
            db.add(source);db.flush()
        turn_id=sid(tenant,'TURN-'+key);turn=db.get(Turn,turn_id)
        sig_id=sid(tenant,'SIG-'+key) if need_spec else None
        if not turn:
            kb_key=ROUTE_KB.get(route,'');kb_id=sid(tenant,'KB-'+kb_key) if kb_key else ''
            kb_src=db.get(Source,kb_id) if kb_id else None
            out={'source_ids':[kb_id] if kb_src else [],'signal_id':sig_id or None,'message_source_id':source.id,'model_calls':0,'schema_version':'rm-turn-v2','prompt_version':PROMPT_VERSION,'session_id':session.id,'sharing_status':'SHARED' if sig_id else 'HELP_ONLY','capture_method':'INSTITUTION_POLICY','suggestions':[]}
            turn=Turn(id=turn_id,tenant_id=tenant,conversation_id=conv.id,party_id=party.id,actor_id=actor_id,request_key='seed-turn-'+key,payload_hash=hash_payload({'seed':persona,'n':n}),message=message,answer=answer,status='COMPLETED',route=route,mode='SIMULATED',model=LOCAL_MODEL,share=True,output_json=j(out),tools_json='[]',latency_ms=0,created_at=t_time)
            db.add(turn);db.flush()
        if not db.query(SessionTurn).filter_by(id=turn.id,tenant_id=tenant,session_id=session.id).first():
            db.add(SessionTurn(id=turn.id,tenant_id=tenant,session_id=session.id));db.flush()
        if need_spec:
            category,urgency,sig_title,need_text=need_spec
            sig=db.get(Signal,sig_id)
            if not sig:
                sig=Signal(id=sig_id,tenant_id=tenant,party_id=party.id,source_id=source.id,turn_id=turn.id,owner_id=party.owner_id,semantic_key='SEED-'+key,category=category,urgency=urgency,evidence='OBSERVED',workflow='NEW',review='PROPOSED',title=sig_title,need=need_text,rationale='Customer message supports this specific reviewable task; no purchase probability or financial authority inferred.',uncertainty='Needs and permitted next action require RM review; no product activation or transaction result is inferred.',confirmed=False,version=1,created_at=t_time,updated_at=t_time)
                db.add(sig);db.flush()
    db.commit()
    nabila_sig=db.get(Signal,sid(tenant,'SIG-NABILA-1'))
    if nabila_sig:
        from ..core.security import CurrentUser
        from ..routers.rm import review_signal
        from ..routers.engagement import signal_followup,update_followup
        from ..schemas.rm import RMReview,RMStartJourney,RMFollowupUpdate
        maya=CurrentUser(user_id='usr-maya',name='Maya Putri',email='maya.putri@nusantarafinance.co.id',role='RM',tenant_id='demo-bank',institution_type='BANK')
        if nabila_sig.review=='PROPOSED':
            review_signal(nabila_sig.id,RMReview(base_version=nabila_sig.version,decision='ACCEPTED',confirmed=True),db,maya)
            db.refresh(nabila_sig)
        j_row=db.query(Journey).filter_by(tenant_id=tenant,signal_id=nabila_sig.id,kind='RM_FOLLOWUP').first()
        if not j_row:
            j_res=signal_followup(nabila_sig.id,RMStartJourney(base_version=nabila_sig.version,request_key='seed-nabila-card-followup'),db,maya)
            j_row=db.get(Journey,j_res['id'])
        if j_row and j_row.status=='PLANNED':
            jkt_now=utc_now().astimezone(timezone(timedelta(hours=7)))
            tomorrow=(jkt_now+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
            update_followup(j_row.id,RMFollowupUpdate(base_version=j_row.version,request_key='seed-nabila-card-start',action='START',note='Checking the card courier status with operations.',due_at=tomorrow.isoformat()),db,maya)
    aruna_p=db.get(Prospect,sid(tenant,'P-ARUNA'))
    if aruna_p:aruna_p.need_reviewed=True
    surya_pid=sid(tenant,'SURYA')
    if not db.get(Party,surya_pid):
        db.add(Party(id=surya_pid,tenant_id=tenant,kind='ORGANIZATION',name='PT Surya Mandiri Logistik',segment='BUSINESS',owner_id='usr-maya',relationship='NO_MATCH_IN_AVAILABLE_DATA',identity='CONFIRMED',contact='ALLOWED',locality='Bekasi Selatan',customer_ref=None,context_json=j({'mode':'SYNTHETIC','source':'Synthetic authorized relationship record','products':[],'sector':'Logistics & Distribution','contact_channel':'EMAIL','contact_purpose':'Opt-in commercial collections discussion','email':'surya.logistik@example.invalid'})))
        db.flush()
    surya_need='We would like to discuss collections and corporate merchant facilities for our delivery fleet.'
    surya_src=db.get(Source,sid(tenant,'P-SURYA-SRC'))
    if not surya_src:
        db.add(Source(id=sid(tenant,'P-SURYA-SRC'),tenant_id=tenant,party_id=surya_pid,kind='SYNTHETIC_OPT_IN',title='Opt-in fleet collections enquiry',content=surya_need,content_hash=hashlib.sha256(surya_need.encode()).hexdigest(),mode='SIMULATED',version=1,event_at=now-timedelta(days=2),ingested_at=now-timedelta(days=2)))
        db.flush()
    surya_p=db.get(Prospect,sid(tenant,'P-SURYA'))
    if not surya_p:
        db.add(Prospect(id=sid(tenant,'P-SURYA'),tenant_id=tenant,party_id=surya_pid,source_id=sid(tenant,'P-SURYA-SRC'),owner_id='usr-maya',state='ASSIGNED',disposition=None,latitude='-6.242000',longitude='106.982000',reasons_json=j(['Explicit collections and merchant discussion request','Commercial fleet logistics fits priority tier']),need=surya_need,need_reviewed=True,import_key='synthetic-v1-P-SURYA'))
    else:surya_p.need_reviewed=True
    makmur_pid=sid(tenant,'MAKMUR')
    if not db.get(Party,makmur_pid):
        db.add(Party(id=makmur_pid,tenant_id=tenant,kind='ORGANIZATION',name='Toko Makmur Sentosa',segment='BUSINESS',owner_id='usr-maya',relationship='NO_MATCH_IN_AVAILABLE_DATA',identity='CONFIRMED',contact='ALLOWED',locality='Bekasi Timur',customer_ref=None,context_json=j({'mode':'SYNTHETIC','source':'Synthetic authorized relationship record','products':[],'sector':'Retail & Consumer Goods','contact_channel':'EMAIL','contact_purpose':'Working capital inquiry','email':'makmur.sentosa@example.invalid'})))
        db.flush()
    makmur_need='We would like to explore working capital and merchant facilities for store inventory.'
    makmur_time=now-timedelta(days=42)
    makmur_src=db.get(Source,sid(tenant,'P-MAKMUR-SRC'))
    if not makmur_src:
        db.add(Source(id=sid(tenant,'P-MAKMUR-SRC'),tenant_id=tenant,party_id=makmur_pid,kind='SYNTHETIC_OPT_IN',title='Prior commercial enquiry',content=makmur_need,content_hash=hashlib.sha256(makmur_need.encode()).hexdigest(),mode='SIMULATED',version=1,event_at=makmur_time,ingested_at=makmur_time))
        db.flush()
    else:makmur_src.event_at=makmur_time
    if not db.get(Prospect,sid(tenant,'P-MAKMUR')):
        db.add(Prospect(id=sid(tenant,'P-MAKMUR'),tenant_id=tenant,party_id=makmur_pid,source_id=sid(tenant,'P-MAKMUR-SRC'),owner_id='usr-maya',state='ASSIGNED',disposition=None,latitude='-6.248000',longitude='106.991000',reasons_json=j(['Prior opt-in enquiry recorded 42 days ago','Source outside 30-day window; refresh needed']),need=makmur_need,need_reviewed=False,import_key='synthetic-v1-P-MAKMUR'))
    db.commit()
