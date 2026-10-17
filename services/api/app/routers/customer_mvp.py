"""Focused customer surfaces and observed behavior for assigned RMs."""
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import CurrentUser,get_current_user
from ..services.rm import party_for,require_rm
from ..services.customer_activity import rm_contact,record_activity,behavior
from ..schemas.rm import RMRMContact,RMActivityRequest,RMActivityReceipt,RMBehavior
router=APIRouter(prefix='/v1/rm',tags=['customer-mvp'])

@router.get('/chat/{pid}/rm-contact',response_model=RMRMContact)
def contact(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,pid,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'An own existing person relationship is required.')
    return rm_contact(db,user,p)

@router.post('/chat/{pid}/activity',response_model=RMActivityReceipt)
def activity(pid:str,req:RMActivityRequest,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    p=party_for(db,user,pid,customer=True)
    if p.kind!='PERSON' or p.relationship!='EXISTING_CUSTOMER':raise HTTPException(403,'An own existing person relationship is required.')
    row=record_activity(db,user,p,req.kind,req.product,req.request_key);db.commit()
    return {'id':row.id,'signal_id':row.signal_id,'mode':row.mode,'message':'Observed activity recorded; no financial action or outbound message.'}

@router.get('/parties/{pid}/behavior',response_model=RMBehavior)
def activity_history(pid:str,db:Session=Depends(get_db),user:CurrentUser=Depends(get_current_user)):
    require_rm(user);return behavior(db,user,party_for(db,user,pid))
