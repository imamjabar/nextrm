"""Bounded local synthetic CSV adapter, deliberately separate from live provider sourcing."""
import csv,io,json,hashlib,os
from decimal import Decimal,InvalidOperation
from fastapi import HTTPException
from ..models.relationships import Party,Source,Prospect,ContactLink
from .rm import uid,j,require_rm
from .customer_match import match_place
def import_csv(db,user,csv_text,request_key):
    require_rm(user)
    if os.getenv('ENVIRONMENT','development') not in {'development','test'} or user.data_mode!='SYNTHETIC':raise HTTPException(403,'Synthetic CSV import is restricted to the local synthetic environment.')
    payload_hash=hashlib.sha256(csv_text.encode()).hexdigest();batchid=user.tenant_id+'-batch-'+hashlib.sha256((user.user_id+':'+request_key).encode()).hexdigest()[:20]
    prior=db.query(Source).filter_by(id=batchid,tenant_id=user.tenant_id,kind='IMPORT_BATCH').first()
    if prior:
        saved=json.loads(prior.content)
        if saved['payload_hash']!=payload_hash:raise HTTPException(409,'This import key was used for different content.')
        return saved['result']
    reader=csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
    allowed={'external_id','source_version','kind','name','locality','need','latitude','longitude','contact_name','contact_role','contact_email','identity_reviewed','contact_allowed','source'}
    if not reader.fieldnames or not {'external_id','kind','name','need','latitude','longitude'}.issubset(reader.fieldnames):raise HTTPException(422,'Required CSV columns: external_id,kind,name,need,latitude,longitude.')
    if len(set(reader.fieldnames))!=len(reader.fieldnames):raise HTTPException(422,'Duplicate CSV column names are not permitted.')
    if set(reader.fieldnames)-allowed:raise HTTPException(422,'Unknown CSV columns are not permitted; owner/tenant/role cannot be reassigned by an import.')
    rows=list(reader)
    if not 1<=len(rows)<=25:raise HTTPException(422,'Import one to 25 synthetic rows at a time.')
    # Validate the whole batch before any writes.
    for i,row in enumerate(rows,1):
        if None in row or any(v is None for v in row.values()):raise HTTPException(422,f'Row {i}: CSV column count does not match the header.')
        if len(row['external_id'])>60:raise HTTPException(422,'External ID must be at most 60 characters.')
        if row['kind'] not in {'PERSON','ORGANIZATION'} or not 2<=len(row['name'].strip())<=160 or not 3<=len(row['need'].strip())<=1200 or not row['external_id'].strip():raise HTTPException(422,f'Row {i}: invalid kind, name, need or external ID.')
        try:
            lat=Decimal(row['latitude']);lng=Decimal(row['longitude'])
            if not lat.is_finite() or not lng.is_finite() or not -90<=lat<=90 or not -180<=lng<=180:raise ValueError()
        except (ValueError,InvalidOperation):raise HTTPException(422,f'Row {i}: valid finite locality coordinates are required.')
        email=row.get('contact_email','').strip()
        if email and not email.endswith('@example.invalid'):raise HTTPException(422,'Local synthetic imports require contact emails ending @example.invalid; do not upload private contacts.')
    imported=[];reused=0;matched_existing=0;held_for_review=0
    for row in rows:
        external='csv:'+row['external_id'].strip()+':'+(row.get('source_version') or '1');rowhash=hashlib.sha256(j(row).encode()).hexdigest()
        old=db.query(Prospect).filter_by(tenant_id=user.tenant_id,import_key=external).first()
        if old:
            if old.owner_id!=user.user_id:raise HTTPException(403,'Source record is outside your permitted assignment.')
            source=db.query(Source).filter_by(id=old.source_id,tenant_id=user.tenant_id).one()
            if source.content_hash!=rowhash:raise HTTPException(409,'Existing external record changed without a new source_version; no partial batch committed.')
            imported.append(old.id);reused+=1;continue
        match=match_place(db,user.tenant_id,name=row['name'].strip(),email=row.get('contact_email','').strip() or None,latitude=row['latitude'],longitude=row['longitude'],address=row.get('locality'))
        if match['status']=='EXISTING_CUSTOMER':
            matched_existing+=1;continue
        identity='CONFIRMED' if row.get('identity_reviewed','').lower() in {'true','yes','1'} else 'UNRESOLVED'
        contact='ALLOWED' if row.get('contact_allowed','').lower() in {'true','yes','1'} else 'REQUIRES_CONFIRMATION'
        relationship='NO_MATCH_IN_AVAILABLE_DATA';disposition=None
        reasons=['Supplied synthetic candidate; inspect source and missing information.','Contact and identity remain separate checks.']
        if match['status']=='POSSIBLE_MATCH':
            held_for_review+=1;identity='UNRESOLVED';relationship='POSSIBLE_MATCH';disposition='NEEDS_IDENTITY_REVIEW'
            reasons.extend(match.get('reasons',[]))
        context={'mode':'SYNTHETIC','products':[],'declared_goal':'','notes':'','source':'Operator-supplied synthetic CSV; reviewed flags are fixture assertions, not KYC.','email':row.get('contact_email',''),'contact_channel':'EMAIL' if row.get('contact_email') else 'IN_APP','contact_purpose':'Explicit synthetic opt-in discussion' if contact=='ALLOWED' else 'Permission not confirmed'}
        party=Party(id=uid('PARTY'),tenant_id=user.tenant_id,kind=row['kind'],name=row['name'].strip(),segment='RETAIL' if row['kind']=='PERSON' else 'BUSINESS',owner_id=user.user_id,relationship=relationship,identity=identity,contact=contact,locality=row.get('locality') or 'Synthetic locality',context_json=j(context))
        db.add(party);db.flush()
        source=Source(id=uid('SOURCE'),tenant_id=user.tenant_id,party_id=party.id,kind='SYNTHETIC_CSV',title=row.get('source') or 'Operator-supplied synthetic CSV',content=j(row),content_hash=rowhash,mode='SIMULATED')
        db.add(source);db.flush()
        prospect=Prospect(id=uid('PROSPECT'),tenant_id=user.tenant_id,party_id=party.id,source_id=source.id,owner_id=user.user_id,latitude=row['latitude'],longitude=row['longitude'],need=row['need'],reasons_json=j(reasons),import_key=external,disposition=disposition)
        db.add(prospect)
        if row['kind']=='ORGANIZATION' and row.get('contact_name'):
            person=Party(id=uid('CONTACT'),tenant_id=user.tenant_id,kind='PERSON',name=row['contact_name'].strip(),segment='BUSINESS_CONTACT',owner_id=user.user_id,relationship='NO_MATCH_IN_AVAILABLE_DATA',identity='UNRESOLVED',contact='REQUIRES_CONFIRMATION',locality=party.locality,context_json=j({'mode':'SYNTHETIC','products':[],'notes':'','email':''}))
            db.add(person);db.flush();db.add(ContactLink(id=uid('LINK'),tenant_id=user.tenant_id,organization_id=party.id,person_id=person.id,role=row.get('contact_role') or 'Business contact',source_ref=source.id,details_json=j({'contact_email':row.get('contact_email',''),'authority':'NOT_ESTABLISHED','mode':'SYNTHETIC'})))
        imported.append(prospect.id)
    result={'imported':len(imported)-reused,'reused':reused,'prospect_ids':imported,'mode':'SIMULATED','matched_existing':matched_existing,'held_for_review':held_for_review}
    content=j({'payload_hash':payload_hash,'result':result});db.add(Source(id=batchid,tenant_id=user.tenant_id,kind='IMPORT_BATCH',title='Synthetic CSV import receipt',content=content,content_hash=hashlib.sha256(content.encode()).hexdigest(),mode='SIMULATED'));db.commit();return result
