import os
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .config import ENVIRONMENT
from .database import get_db
from ..models.entities import UserAssignmentModel, InstitutionModel

class CurrentUser(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    tenant_id: str
    institution_type: str
    entity_id: Optional[str] = None
    institution_name: str = ""
    data_mode: str = "SYNTHETIC"

DEMO_USERS = {
    "usr-maya": CurrentUser(
        user_id="usr-maya",
        name="Maya Putri",
        email="maya.putri@nusantarafinance.co.id",
        role="RM",
        tenant_id="demo-bank",
        institution_type="BANK"
    ),
    "usr-dina": CurrentUser(
        user_id="usr-dina",
        name="Dina Rahma",
        email="dina@example.invalid",
        role="CUSTOMER",
        tenant_id="demo-bank",
        institution_type="BANK"
    ),
    "usr-aditya": CurrentUser(
        user_id="usr-aditya",
        name="Aditya Pratama",
        email="aditya@example.invalid",
        role="CUSTOMER",
        tenant_id="demo-bank",
        institution_type="BANK"
    ),
    "usr-nabila": CurrentUser(
        user_id="usr-nabila",
        name="Nabila Aulia",
        email="nabila@example.invalid",
        role="CUSTOMER",
        tenant_id="demo-bank",
        institution_type="BANK"
    ),
    "usr-quality": CurrentUser(
        user_id="usr-quality",
        name="Intan · Quality reviewer",
        email="quality@example.invalid",
        role="QUALITY_REVIEWER",
        tenant_id="demo-bank",
        institution_type="BANK"
    ),
    "usr-aiadmin": CurrentUser(
        user_id="usr-aiadmin",
        name="Arif · AI operations",
        email="aiadmin@example.invalid",
        role="INSTITUTION_AI_ADMIN",
        tenant_id="demo-bank",
        institution_type="BANK"
    )
}

def verify_firebase_token(token: str):
    """Firebase Admin verifies signature, audience, issuer, expiry and revocation."""
    if token.count(".") != 2:
        raise ValueError("Malformed signed identity token")
    import firebase_admin
    from firebase_admin import auth
    try:
        application = firebase_admin.get_app()
    except ValueError:
        application = firebase_admin.initialize_app()
    return auth.verify_id_token(token, app=application, check_revoked=True)

def verified_uid(authorization: Optional[str]=Header(None),x_user_id:Optional[str]=Header(None,alias='X-User-Id')) -> str:
    is_prod=ENVIRONMENT=='production' or os.getenv('AUTH_PROVIDER','').lower()=='firebase'
    if authorization:
        if not authorization.startswith('Bearer '):raise HTTPException(401,'Sign in required')
        try:return verify_firebase_token(authorization[7:])['uid']
        except Exception:raise HTTPException(401,'Your session expired or could not be verified. Sign in again.')
    if x_user_id in DEMO_USERS and not is_prod and ENVIRONMENT in {'development','test'}:return x_user_id
    raise HTTPException(401,'Verified sign-in required')

def institution_access(db,tenant_id):
    from datetime import datetime,timezone
    from ..models.entities import InstitutionAccessModel
    inst=db.get(InstitutionModel,tenant_id)
    if not inst:raise HTTPException(403,'Institution unavailable')
    access=db.get(InstitutionAccessModel,tenant_id)
    if access:
        expiry=access.expires_at.replace(tzinfo=timezone.utc) if access.expires_at.tzinfo is None else access.expires_at
        if access.status!='ACTIVE' or expiry<=datetime.now(timezone.utc):raise HTTPException(403,'POC access has ended or been suspended. Contact your institution administrator.')
    elif tenant_id != 'demo-bank' and (ENVIRONMENT=='production' or os.getenv('AUTH_PROVIDER','').lower()=='firebase'):
        raise HTTPException(403,'Institution access has not been provisioned')
    return inst

def get_current_user(
    db:Session=Depends(get_db),
    resolved_user_id:str=Depends(verified_uid),
    x_tenant_id:Optional[str]=Header(None,alias='X-Tenant-Id'),
    authorization:Optional[str]=Header(None)
) -> CurrentUser:
    # Resolve from authoritative database
    assignments = db.query(UserAssignmentModel).filter(
        UserAssignmentModel.user_id == resolved_user_id,
        UserAssignmentModel.active == True
    ).all()
    if x_tenant_id:
        matching = [a for a in assignments if a.tenant_id == x_tenant_id]
        if assignments and not matching:
            raise HTTPException(403, "Cross-tenant access denied")
        assignments = matching
    if len(assignments) > 1:
        raise HTTPException(400, "Select an authorized tenant membership")
    assignment = assignments[0] if assignments else None
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User identity '{resolved_user_id}' unverified, inactive, or not found in authorized tenant directory."
        )

    # Invariant: request-supplied tenant ID is NEVER trusted alone.
    # Must match the user's authorized tenant!
    if x_tenant_id and assignment.tenant_id != x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access denied: User belongs to tenant '{assignment.tenant_id}', attempted to access '{x_tenant_id}'."
        )

    inst=institution_access(db,assignment.tenant_id)
    if not authorization and assignment.tenant_id != 'demo-bank':
        raise HTTPException(401,'POC accounts require verified sign-in')
    institution_type=inst.institution_type
    from ..models.entities import InstitutionAccessModel
    access_record=db.get(InstitutionAccessModel,inst.id)
    data_mode=access_record.data_mode if access_record else "SYNTHETIC"

    return CurrentUser(
        user_id=assignment.user_id,
        name=assignment.name,
        email=assignment.email,
        role=assignment.role,
        tenant_id=assignment.tenant_id,
        institution_type=institution_type,
        institution_name=inst.name,
        entity_id=assignment.entity_id,
        data_mode=data_mode
    )

def require_role(*allowed_roles: str):
    def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of roles {allowed_roles}, but current user role is '{current_user.role}'."
            )
        return current_user
    return role_checker

def require_internal_staff(current_user: CurrentUser = Depends(get_current_user)):
    """Denies borrowers from reading internal underwriting packets, memos, and financial alternatives."""
    if current_user.role not in {"RM","QUALITY_REVIEWER","INSTITUTION_AI_ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Internal staff access required."
        )
    return current_user

