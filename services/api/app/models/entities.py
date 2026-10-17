from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
)
from ..core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class InstitutionModel(Base):
    __tablename__ = "institutions"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    institution_type = Column(String(20), nullable=False)
    policy_pack_id = Column(String(50), default="default-policy")
    policy_version = Column(String(20), default="1.0.0")
    approval_mode = Column(String(30), default="SANDBOX_LOCAL")
    created_at = Column(DateTime, default=utc_now)

class UserAssignmentModel(Base):
    __tablename__ = "user_assignments"

    id = Column(String(50), primary_key=True)
    user_id = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False)
    tenant_id = Column(String(50), ForeignKey("institutions.id"), nullable=False)
    entity_id = Column(String(50), nullable=True)
    active = Column(Boolean, default=True)

class InstitutionAccessModel(Base):
    __tablename__ = 'institution_access'

    tenant_id = Column(String(50), ForeignKey('institutions.id'), primary_key=True)
    status = Column(String(20), nullable=False, default='ACTIVE')
    expires_at = Column(DateTime(timezone=True), nullable=False)
    data_mode = Column(String(20), nullable=False, default='SYNTHETIC')
