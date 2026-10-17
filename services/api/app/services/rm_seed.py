"""Explicit repeat-safe, synthetic person/business fixtures. No production sourcing."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from ..models.entities import InstitutionModel,UserAssignmentModel
from ..models.relationships import Party,ContactLink,Source,Prospect,Signal,QualityGrant,Nudge
ROOT=Path(__file__).resolve().parents[4]

def sid(tenant,suffix): return hashlib.sha256(tenant.encode()).hexdigest()[:8]+'-'+suffix

def seed_relationships(db):
    for inst in db.query(InstitutionModel).filter_by(institution_type='BANK').all():
        rm=db.query(UserAssignmentModel).filter_by(tenant_id=inst.id,role='RM',active=True).first()
        if not rm: continue
        tenant=inst.id;owner=rm.user_id
        def party(key,name,kind='PERSON',relationship='EXISTING_CUSTOMER',identity='CONFIRMED',contact='ALLOWED',segment='RETAIL',locality='Bekasi',extra=None):
            pid=sid(tenant,key)
            if not db.get(Party,pid):
                ctx={'mode':'SYNTHETIC','source':'Synthetic authorized relationship record','products':['Everyday savings'] if relationship=='EXISTING_CUSTOMER' and kind=='PERSON' else [],'notes':'','why_now':'','contact_channel':'IN_APP','contact_purpose':'Requested needs/service discussion','email':key+'@example.invalid'}
                ctx.update(extra or {})
                db.add(Party(id=pid,tenant_id=tenant,kind=kind,name=name,segment=segment,owner_id=owner,relationship=relationship,identity=identity,contact=contact,locality=locality,customer_ref=('C-'+key if relationship=='EXISTING_CUSTOMER' else None),context_json=json.dumps(ctx)))
            return pid
        dina=party('DINA','Dina Rahma',extra={'occupation':'Teacher','declared_goal':'Preparing for school expenses','notes':'Internal RM note: discuss only the need the customer confirms.'})
        aditya=party('ADITYA','Aditya Pratama',locality='Jakarta Selatan',extra={'occupation':'Engineer','products':['Everyday savings','Term deposit'],'declared_goal':'Liquidity planning','maturity_date':'2026-10-15'})
        nabila=party('NABILA','Nabila Aulia',locality='Tangerang',extra={'occupation':'Designer','declared_goal':'Keep everyday banking simple'})
        org=party('SINAR','PT Sinar Distribusi','ORGANIZATION',segment='BUSINESS',extra={'products':['Business transaction account'],'legacy_case':'CF-026' if tenant=='demo-bank' else None})
        saricontact=party('SARI-CONTACT','Sari Wulandari',relationship='NO_MATCH_IN_AVAILABLE_DATA',segment='BUSINESS_CONTACT',extra={'occupation':'Finance manager','products':[],'notes':''})
        aruna=party('ARUNA','CV Aruna Niaga','ORGANIZATION','NO_MATCH_IN_AVAILABLE_DATA',segment='BUSINESS',extra={'sector':'Retail distribution','contact_channel':'EMAIL','contact_purpose':'Opt-in business collections enquiry'})
        bayu=party('BAYU-CONTACT','Bayu Saputra',relationship='NO_MATCH_IN_AVAILABLE_DATA',segment='BUSINESS_CONTACT',extra={'occupation':'Director','products':[],'notes':''})
        ratna=party('RATNA-CONTACT','Ratna Dewi',relationship='NO_MATCH_IN_AVAILABLE_DATA',contact='REQUIRES_CONFIRMATION',segment='BUSINESS_CONTACT',extra={'occupation':'Operations lead','products':[],'notes':''})
        retail=party('RANI','Rani Kusuma',relationship='NO_MATCH_IN_AVAILABLE_DATA',extra={'occupation':'Freelancer','contact_purpose':'Opt-in savings enquiry','declared_goal':'Emergency savings','products':[]})
        retail2=party('BIMA','Bima Setiawan',relationship='NO_MATCH_IN_AVAILABLE_DATA',locality='Depok',extra={'occupation':'Retail employee','contact_purpose':'Authorized referral for salary-account discussion','products':[]})
        ambiguous=party('RANTAI','PT Rantai Pasok Utama','ORGANIZATION','UNKNOWN','AMBIGUOUS','RESTRICTED','BUSINESS',extra={'products':[],'candidate_note':'Two similarly named legal entities remain separate; no automatic match.'})
        blocked=party('SINTA','Sinta Maharani',relationship='NO_MATCH_IN_AVAILABLE_DATA',contact='RESTRICTED',extra={'products':[],'contact_reason':'Do not contact preference on source record.'})
        db.flush()
        for item in json.loads((ROOT/'data/synthetic/rm/knowledge.json').read_text()):
            sourceid=sid(tenant,'KB-'+item['key'])
            existing=db.get(Source,sourceid);digest=hashlib.sha256(item['body'].encode()).hexdigest()
            if not existing:db.add(Source(id=sourceid,tenant_id=tenant,kind='APPROVED_KNOWLEDGE',title=item['title'],content=item['body'],content_hash=digest,mode='SIMULATED'))
            elif existing.content_hash!=digest:existing.title=item['title'];existing.content=item['body'];existing.content_hash=digest;existing.version=(existing.version or 1)+1
        def source(key,pid,title,content,kind='SYNTHETIC_OPT_IN'):
            sourceid=sid(tenant,key)
            if not db.get(Source,sourceid):db.add(Source(id=sourceid,tenant_id=tenant,party_id=pid,kind=kind,title=title,content=content,content_hash=hashlib.sha256(content.encode()).hexdigest(),mode='SIMULATED'))
            db.flush()
            return sourceid
        for key,pid,route,title,body,prompt in [
            ('NUDGE-SCHOOL',dina,'SAVINGS','A plan for school expenses',
             'You mentioned preparing for school expenses. Explore how to keep planned expenses separate from everyday spending.',
             'How can I plan accessible savings for school expenses?'),
            ('NUDGE-LIQUIDITY',aditya,'DEPOSIT','Plan your next liquidity conversation',
             'Your stated goal is liquidity planning. Understand access, maturity and withdrawal conditions before considering a deposit.',
             'What should I check about deposit maturity and access to my money?'),
            ('NUDGE-HELP',nabila,'SERVICE','Make everyday banking easier',
             'You said you want to keep everyday banking simple. Ask about a payment or request help from your RM.',
             'How do I check a payment status safely?')]:
            context=json.loads(db.get(Party,pid).context_json)
            src=source(key+'-CONTEXT',pid,'Synthetic declared customer goal',context.get('declared_goal',''),'SYNTHETIC_CUSTOMER_CONTEXT')
            nid=sid(tenant,key)
            if not db.get(Nudge,nid):
                db.add(Nudge(id=nid,tenant_id=tenant,party_id=pid,source_id=src,knowledge_id=sid(tenant,'KB-'+{'SAVINGS':'savings','DEPOSIT':'deposit','SERVICE':'payments'}[route]),route=route,title=title,body=body,prompt=prompt,state='AVAILABLE',version=1))
        db.flush()
        for key,orgid,pid,role in [('C-SINAR',org,saricontact,'Finance manager'),('C-ARUNA-DIR',aruna,bayu,'Director / board contact'),('C-ARUNA-OPS',aruna,ratna,'Operations contact')]:
            contact_person=db.get(Party,pid);contact_email=json.loads(contact_person.context_json).get('email','')
            src=source(key,orgid,'Synthetic company contact record',contact_person.name+' · '+contact_email+' · '+role+' is recorded in the supplied company contact fixture. It does not establish signing authority or authorize personal-account access.','SYNTHETIC_COMPANY_CONTACT')
            if not db.get(ContactLink,sid(tenant,key)):db.add(ContactLink(id=sid(tenant,key),tenant_id=tenant,organization_id=orgid,person_id=pid,role=role,source_ref=src,details_json=json.dumps({'authority':'NOT_ESTABLISHED','mode':'SYNTHETIC','contact_email':contact_email})))
        rows=[('P-ARUNA',aruna,'Opt-in campaign enquiry','We would like help identifying incoming customer payments for our shop. Please arrange a discussion.',-6.238,106.989,['Customer asked for a business collections discussion','Distribution segment fits the configured service']),('P-RANI',retail,'Opt-in retail enquiry','I want to understand savings for an emergency fund. An RM conversation would help.',-6.251,106.974,['Explicit savings question from a person','Contact is allowed for the requested conversation']),('P-BIMA',retail2,'Authorized retail referral','I would like to discuss a salary account and everyday banking.',-6.279,106.960,['Authorized referral with requested discussion','Retail needs are a hypothesis until confirmed']),('P-RANTAI',ambiguous,'Synthetic partner list','A company name occurs in a partner list; entity identity and need are unconfirmed.',-6.260,106.998,['Identity must be resolved before action','No confirmed current need']),('P-SINTA',blocked,'Synthetic permission record','Do not contact for marketing or product outreach.',-6.226,106.960,['Contact restricted; retain the refusal','No commercial action permitted']),('P-SINAR',org,'Synthetic CRM relationship match','This party is already an institution customer; do not duplicate acquisition outreach.',-6.218,106.985,['Existing relationship matched in the available CRM','Route distinct new needs into relationship work'])]
        for key,pid,title,need,lat,lng,reasons in rows:
            src=source(key+'-SRC',pid,title,need)
            if not db.get(Prospect,sid(tenant,key)):
                matched=pid==org
                db.add(Prospect(id=sid(tenant,key),tenant_id=tenant,party_id=pid,source_id=src,owner_id=owner,state='ASSIGNED',disposition='EXISTING_CUSTOMER' if matched else None,latitude=str(lat),longitude=str(lng),reasons_json=json.dumps(reasons),need=need,import_key='synthetic-v1-'+key))
        for key,pid,title,need,category,urgency in [('S-MATURITY',aditya,'Term deposit maturity approaching','Customer goal and upcoming liquidity needs are not yet confirmed.','GUIDANCE','TIME_SENSITIVE'),('S-CARD',nabila,'Customer requests card-delivery help','I would like help checking the status of my card delivery.','SERVICE_ISSUE','ROUTINE')]:
            src=source(key+'-SRC',pid,'Synthetic authorized event / customer note',need,'SYNTHETIC_CUSTOMER_EVENT')
            if not db.get(Signal,sid(tenant,key)):db.add(Signal(id=sid(tenant,key),tenant_id=tenant,party_id=pid,source_id=src,owner_id=owner,semantic_key=key,category=category,urgency=urgency,evidence='OBSERVED',title=title,need=need,rationale='Authorized synthetic event needs an appropriate RM response.',uncertainty='Further details and customer preferences require confirmation.'))
        if tenant=='demo-bank':
            for uid,name,role,entity in [('usr-dina','Dina Rahma','CUSTOMER',dina),('usr-quality','Intan · Quality reviewer','QUALITY_REVIEWER',None),('usr-aiadmin','Arif · AI operations','INSTITUTION_AI_ADMIN',None)]:
                if not db.query(UserAssignmentModel).filter_by(user_id=uid,tenant_id=tenant).first():db.add(UserAssignmentModel(id='ua-'+uid,user_id=uid,name=name,email=uid+'@example.invalid',role=role,tenant_id=tenant,entity_id=entity,active=True))
                if role in {'QUALITY_REVIEWER','INSTITUTION_AI_ADMIN'} and not db.query(QualityGrant).filter_by(tenant_id=tenant,user_id=uid).first():db.add(QualityGrant(id=sid(tenant,'GRANT-'+uid),tenant_id=tenant,user_id=uid,content=role=='QUALITY_REVIEWER',party_scope_json=json.dumps([dina,aditya,nabila]),purpose='Explicit synthetic-demo evaluation/content review' if role=='QUALITY_REVIEWER' else 'Institution-scoped health and evaluation metadata'))
    from .enrichment import seed_enrichment
    seed_enrichment(db)
    db.commit()
