from fastapi import APIRouter, Depends, HTTPException
from ..core.config import APP_NAME, APP_TAGLINE, APP_VERSION
from ..core.security import CurrentUser, DEMO_USERS, get_current_user

router = APIRouter(prefix="/v1/auth", tags=["auth"])

@router.get("/me")
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    return {
        "app_name": APP_NAME,
        "app_tagline": APP_TAGLINE,
        "app_version": APP_VERSION,
        "user": current_user
    }

@router.get("/demo-users")
def list_demo_personas():
    from ..core.config import ENVIRONMENT
    if ENVIRONMENT not in {"development", "test"}:
        raise HTTPException(404, "Not found")
    return {
        "app_name": APP_NAME,
        "users": [u for u in DEMO_USERS.values() if u.role in {"RM","CUSTOMER","QUALITY_REVIEWER","INSTITUTION_AI_ADMIN"} and u.tenant_id=="demo-bank"]
    }


from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.security import verified_uid,institution_access
from ..models.entities import UserAssignmentModel
class Membership(BaseModel):
    tenant_id:str
    institution_name:str
    role:str
class MembershipsResponse(BaseModel):
    user_id:str
    memberships:list[Membership]
@router.get('/memberships',response_model=MembershipsResponse)
def memberships(uid:str=Depends(verified_uid),db:Session=Depends(get_db)):
    result=[]
    for a in db.query(UserAssignmentModel).filter_by(user_id=uid,active=True):
        try:inst=institution_access(db,a.tenant_id)
        except HTTPException:continue
        result.append(Membership(tenant_id=a.tenant_id,institution_name=inst.name,role=a.role))
    if not result:raise HTTPException(403,'No active workspace is assigned. Contact your institution administrator.')
    return MembershipsResponse(user_id=uid,memberships=result)
