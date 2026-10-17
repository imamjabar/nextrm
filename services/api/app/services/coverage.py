"""Dedicated relationships and bounded shared-case coverage, never one RM for every user."""
from fastapi import HTTPException
from sqlalchemy import or_,func
from ..models.relationships import CustomerCoverage,RMCapacity,Party,Signal,Journey
from ..models.entities import UserAssignmentModel
from .rm import uid
POOL_OWNER='POOL:shared-service'

def coverage_for(db,party):
    row=db.query(CustomerCoverage).filter_by(tenant_id=party.tenant_id,party_id=party.id).first()
    return row

def routing_owner(db,party,escalate=False):
    c=coverage_for(db,party)
    return party.owner_id if not c else c.rm_id if c.mode=='DEDICATED' else 'DIGITAL:'+party.tenant_id if c.mode=='DIGITAL' and not escalate else POOL_OWNER

def can_read(db,user,party):
    c=coverage_for(db,party)
    if not c or c.mode=='DEDICATED':return party.owner_id==user.user_id
    return bool(db.query(Signal).filter_by(tenant_id=user.tenant_id,party_id=party.id,owner_id=user.user_id).filter(Signal.workflow.notin_(['COMPLETED','DISMISSED'])).first() or db.query(Journey).filter_by(tenant_id=user.tenant_id,party_id=party.id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED'])).first())

def capacity_for(db,tenant,user_id,lock=False):
    q=db.query(RMCapacity).filter_by(tenant_id=tenant,user_id=user_id)
    if lock:q=q.with_for_update()
    row=q.first()
    if not row:row=RMCapacity(id=uid('CAPACITY'),tenant_id=tenant,user_id=user_id);db.add(row);db.flush()
    return row

def dedicated_count(db,tenant,user):
    return db.query(Party).outerjoin(CustomerCoverage,CustomerCoverage.party_id==Party.id).filter(Party.tenant_id==tenant,Party.owner_id==user,Party.relationship=='EXISTING_CUSTOMER',or_(CustomerCoverage.id.is_(None),CustomerCoverage.mode=='DEDICATED')).count()

def active_count(db,tenant,user):
    return db.query(Signal).join(CustomerCoverage,CustomerCoverage.party_id==Signal.party_id).filter(Signal.tenant_id==tenant,Signal.owner_id==user,CustomerCoverage.mode!='DEDICATED',Signal.workflow.notin_(['COMPLETED','DISMISSED'])).count()

def owned_ids(db,user):
    return db.query(Party.id).outerjoin(CustomerCoverage,CustomerCoverage.party_id==Party.id).filter(Party.tenant_id==user.tenant_id,Party.owner_id==user.user_id,or_(CustomerCoverage.id.is_(None),CustomerCoverage.mode=='DEDICATED'))

def visible_ids(db,user):
    dedicated=owned_ids(db,user)
    cases=db.query(Signal.party_id).filter(Signal.tenant_id==user.tenant_id,Signal.owner_id==user.user_id,Signal.workflow.notin_(['COMPLETED','DISMISSED']))
    tasks=db.query(Journey.party_id).filter_by(tenant_id=user.tenant_id,actor_id=user.user_id,kind='RM_FOLLOWUP').filter(Journey.status.notin_(['DONE','CANCELLED']))
    return db.query(Party.id).filter(Party.tenant_id==user.tenant_id,or_(Party.id.in_(dedicated),Party.id.in_(cases),Party.id.in_(tasks)))
