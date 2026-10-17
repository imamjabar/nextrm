"""Tenant-owned relationship foundation; separate from preserved credit records."""
from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Numeric, UniqueConstraint, ForeignKey, Index
from ..core.database import Base
from .entities import utc_now

class Party(Base):
    __tablename__='rm_parties'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    kind=Column(String(20),nullable=False); name=Column(String(180),nullable=False); segment=Column(String(40),nullable=False)
    owner_id=Column(String(80),nullable=False,index=True); relationship=Column(String(40),nullable=False); identity=Column(String(20),nullable=False)
    contact=Column(String(30),nullable=False); locality=Column(String(120),nullable=False); customer_ref=Column(String(80),nullable=True)
    context_json=Column(Text,nullable=False,default='{}'); version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(Index('ix_rm_party_tenant_owner','tenant_id','owner_id'),)

class ContactLink(Base):
    __tablename__='rm_contacts'
    id=Column(String(100),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    organization_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False); person_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False)
    role=Column(String(80),nullable=False); source_ref=Column(String(100),nullable=False); details_json=Column(Text,nullable=False,default='{}')
    __table_args__=(UniqueConstraint('tenant_id','organization_id','person_id','role'),)

class Source(Base):
    __tablename__='rm_sources'
    id=Column(String(100),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=True); kind=Column(String(40),nullable=False); title=Column(String(180),nullable=False)
    content=Column(Text,nullable=False); content_hash=Column(String(64),nullable=False); mode=Column(String(20),nullable=False,default='SIMULATED')
    version=Column(Integer,nullable=False,default=1); event_at=Column(DateTime,nullable=False,default=utc_now); ingested_at=Column(DateTime,nullable=False,default=utc_now)

class Prospect(Base):
    __tablename__='rm_prospects'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False); source_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False)
    owner_id=Column(String(80),nullable=False); state=Column(String(40),nullable=False,default='ASSIGNED'); disposition=Column(String(40),nullable=True)
    latitude=Column(Numeric(10,6),nullable=False); longitude=Column(Numeric(10,6),nullable=False)
    reasons_json=Column(Text,nullable=False); need=Column(Text,nullable=False); need_reviewed=Column(Boolean,nullable=False,default=False)
    version=Column(Integer,nullable=False,default=1); import_key=Column(String(100),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','import_key'),)

class Conversation(Base):
    __tablename__='rm_conversations'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False); actor_id=Column(String(80),nullable=False); version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','party_id','actor_id'),)

class Turn(Base):
    __tablename__='rm_turns'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    conversation_id=Column(String(80),ForeignKey('rm_conversations.id'),nullable=False); party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False)
    actor_id=Column(String(80),nullable=False); request_key=Column(String(100),nullable=False); payload_hash=Column(String(64),nullable=False)
    message=Column(Text,nullable=False); answer=Column(Text,nullable=False,default=''); status=Column(String(20),nullable=False,default='PENDING')
    route=Column(String(40),nullable=False,default='PENDING'); mode=Column(String(30),nullable=False); model=Column(String(100),nullable=False)
    share=Column(Boolean,nullable=False); output_json=Column(Text,nullable=False,default='{}'); tools_json=Column(Text,nullable=False,default='[]')
    latency_ms=Column(Integer,nullable=False,default=0); error_code=Column(String(40),nullable=True); created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','actor_id','request_key'),Index('ix_rm_turn_conversation','conversation_id','created_at'))

class Signal(Base):
    __tablename__='rm_signals'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False); source_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False)
    turn_id=Column(String(80),ForeignKey('rm_turns.id'),nullable=True); owner_id=Column(String(80),nullable=False); semantic_key=Column(String(100),nullable=False)
    category=Column(String(30),nullable=False); urgency=Column(String(25),nullable=False); evidence=Column(String(30),nullable=False)
    workflow=Column(String(30),nullable=False,default='NEW'); review=Column(String(25),nullable=False,default='PROPOSED')
    title=Column(String(200),nullable=False); need=Column(Text,nullable=False); rationale=Column(Text,nullable=False); uncertainty=Column(Text,nullable=False)
    confirmed=Column(Boolean,nullable=False,default=False); version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime,nullable=False,default=utc_now); updated_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','party_id','semantic_key'),Index('ix_rm_signal_owner_status','tenant_id','owner_id','workflow'))

class ReviewEvent(Base):
    __tablename__='rm_review_events'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    resource_id=Column(String(80),nullable=False,index=True); actor_id=Column(String(80),nullable=False); action=Column(String(40),nullable=False)
    reason=Column(Text,nullable=False); before_json=Column(Text,nullable=False); after_json=Column(Text,nullable=False); created_at=Column(DateTime,nullable=False,default=utc_now)

class Journey(Base):
    __tablename__='rm_journeys'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False); actor_id=Column(String(80),nullable=False); source_id=Column(String(100),nullable=False)
    signal_id=Column(String(80),nullable=True); prospect_id=Column(String(80),nullable=True); kind=Column(String(40),nullable=False)
    request_key=Column(String(100),nullable=False); payload_hash=Column(String(64),nullable=False); need=Column(Text,nullable=False)
    status=Column(String(40),nullable=False,default='APPLICATION_STARTED'); stage=Column(Integer,nullable=False,default=0); version=Column(Integer,nullable=False,default=1)
    operation_ref=Column(String(100),nullable=False); draft=Column(Text,nullable=False); history_json=Column(Text,nullable=False,default='[]')
    created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','request_key'),UniqueConstraint('tenant_id','signal_id','kind'),UniqueConstraint('tenant_id','prospect_id','kind'))

class QualityGrant(Base):
    __tablename__='rm_quality_grants'
    id=Column(String(100),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    user_id=Column(String(80),nullable=False); content=Column(Boolean,nullable=False,default=False); active=Column(Boolean,nullable=False,default=True)
    purpose=Column(String(160),nullable=False); party_scope_json=Column(Text,nullable=False,default='[]'); __table_args__=(UniqueConstraint('tenant_id','user_id'),)

class EvaluationRun(Base):
    __tablename__='rm_evaluation_runs'
    id=Column(String(80),primary_key=True); tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    actor_id=Column(String(80),nullable=False); request_key=Column(String(100),nullable=False); status=Column(String(25),nullable=False,default='QUEUED')
    suite_version=Column(String(40),nullable=False); config_json=Column(Text,nullable=False,default='{}'); version=Column(Integer,nullable=False,default=1); mode=Column(String(30),nullable=False); results_json=Column(Text,nullable=False,default='[]')
    error=Column(Text,nullable=True); lease_token=Column(String(80),nullable=True); lease_until=Column(DateTime,nullable=True); created_at=Column(DateTime,nullable=False,default=utc_now); updated_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','request_key'),)

class Nudge(Base):
    """A sourced in-app suggestion. Exploring never creates commercial intent."""
    __tablename__='rm_nudges'
    id=Column(String(80),primary_key=True)
    tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False,index=True)
    source_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False)
    knowledge_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False)
    route=Column(String(30),nullable=False)
    title=Column(String(180),nullable=False)
    body=Column(Text,nullable=False)
    prompt=Column(Text,nullable=False)
    state=Column(String(30),nullable=False,default='AVAILABLE')
    version=Column(Integer,nullable=False,default=1)
    signal_id=Column(String(80),ForeignKey('rm_signals.id'),nullable=True)
    created_at=Column(DateTime,nullable=False,default=utc_now)

RM_TABLES=[Party,ContactLink,Source,Prospect,Conversation,Turn,Signal,ReviewEvent,Journey,QualityGrant,EvaluationRun,Nudge]

class EngagementProfile(Base):
    __tablename__='rm_engagement_profiles'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False)
    version=Column(Integer,nullable=False,default=1);data_json=Column(Text,nullable=False,default='{}')
    updated_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','party_id'),)

class SuggestionMeta(Base):
    __tablename__='rm_suggestion_meta'
    id=Column(String(80),ForeignKey('rm_nudges.id'),primary_key=True)
    tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    family=Column(String(8),nullable=False);topic=Column(String(40),nullable=False);category=Column(String(30),nullable=False)
    dependencies_json=Column(Text,nullable=False);expires_at=Column(DateTime,nullable=False)

class EngagementDecision(Base):
    __tablename__='rm_engagement_decisions'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False);digest=Column(String(64),nullable=False)
    data_json=Column(Text,nullable=False);created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','party_id','digest'),)

class EngagementFeedback(Base):
    __tablename__='rm_engagement_feedback'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False);nudge_id=Column(String(80),ForeignKey('rm_nudges.id'),nullable=True)
    action=Column(String(30),nullable=False);request_key=Column(String(100),nullable=False);payload_hash=Column(String(64),nullable=False)
    result_json=Column(Text,nullable=False);created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','party_id','request_key'),)

class FollowupDetail(Base):
    __tablename__='rm_followup_details'
    id=Column(String(80),ForeignKey('rm_journeys.id'),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    snoozed_until=Column(DateTime,nullable=True);outcome=Column(String(40),nullable=True)

class ContactRecord(Base):
    __tablename__='rm_contact_records'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False);actor_id=Column(String(80),nullable=False)
    channel=Column(String(20),nullable=False);purpose=Column(String(30),nullable=False);event=Column(String(30),nullable=False)
    note=Column(Text,nullable=False);source_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False)
    occurred_at=Column(DateTime,nullable=False);created_at=Column(DateTime,nullable=False,default=utc_now)
    request_key=Column(String(100),nullable=False);payload_hash=Column(String(64),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','actor_id','request_key'),)

RM_TABLES.extend([EngagementProfile,SuggestionMeta,EngagementDecision,EngagementFeedback,FollowupDetail,ContactRecord])

class AppActivity(Base):
    """Observed app/source events, independent of confirmed needs or bank outcomes."""
    __tablename__='rm_app_activity'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False,index=True);actor_id=Column(String(80),nullable=False)
    kind=Column(String(40),nullable=False);product=Column(String(20),nullable=False);origin=Column(String(40),nullable=False)
    occurred_at=Column(DateTime,nullable=False);ingested_at=Column(DateTime,nullable=False,default=utc_now)
    request_key=Column(String(100),nullable=False);payload_hash=Column(String(64),nullable=False);mode=Column(String(20),nullable=False)
    source_id=Column(String(100),ForeignKey('rm_sources.id'),nullable=False);signal_id=Column(String(80),ForeignKey('rm_signals.id'),nullable=True)
    __table_args__=(UniqueConstraint('tenant_id','party_id','request_key'),)
RM_TABLES.append(AppActivity)

class GovernanceDraft(Base):
    __tablename__='rm_governance_drafts'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,unique=True)
    version=Column(Integer,nullable=False,default=1);definition_json=Column(Text,nullable=False)
    tested_digest=Column(String(64),nullable=True);test_json=Column(Text,nullable=False,default='[]');updated_at=Column(DateTime,nullable=False,default=utc_now)

class GovernanceRelease(Base):
    __tablename__='rm_governance_releases'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    version=Column(Integer,nullable=False);definition_json=Column(Text,nullable=False);digest=Column(String(64),nullable=False)
    actor_id=Column(String(80),nullable=False);request_key=Column(String(100),nullable=False);created_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','version'),UniqueConstraint('tenant_id','request_key'))

class RMCapacity(Base):
    __tablename__='rm_capacity'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    user_id=Column(String(80),nullable=False);dedicated_limit=Column(Integer,nullable=False,default=200);case_limit=Column(Integer,nullable=False,default=30)
    pool_enabled=Column(Boolean,nullable=False,default=True);version=Column(Integer,nullable=False,default=1)
    __table_args__=(UniqueConstraint('tenant_id','user_id'),)

class CustomerCoverage(Base):
    __tablename__='rm_customer_coverage'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False);mode=Column(String(20),nullable=False)
    rm_id=Column(String(80),nullable=True);pool_id=Column(String(80),nullable=False,default='shared-service')
    tier=Column(String(30),nullable=False,default='STANDARD');version=Column(Integer,nullable=False,default=1)
    __table_args__=(UniqueConstraint('tenant_id','party_id'),)

class ChatSession(Base):
    """Multiple customer sessions, including a non-destructive legacy adapter."""
    __tablename__='rm_chat_sessions'
    id=Column(String(80),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    party_id=Column(String(80),ForeignKey('rm_parties.id'),nullable=False);actor_id=Column(String(80),nullable=False)
    title=Column(String(120),nullable=False,default='New conversation');version=Column(Integer,nullable=False,default=1)
    request_key=Column(String(100),nullable=False);archived=Column(Boolean,nullable=False,default=False)
    created_at=Column(DateTime,nullable=False,default=utc_now);updated_at=Column(DateTime,nullable=False,default=utc_now)
    __table_args__=(UniqueConstraint('tenant_id','actor_id','request_key'),Index('ix_rm_session_subject_time','tenant_id','party_id','actor_id','updated_at','id'))

class SessionTurn(Base):
    __tablename__='rm_session_turns'
    id=Column(String(80),ForeignKey('rm_turns.id'),primary_key=True);tenant_id=Column(String(50),ForeignKey('institutions.id'),nullable=False,index=True)
    session_id=Column(String(80),ForeignKey('rm_chat_sessions.id'),nullable=False,index=True)

RM_TABLES.extend([GovernanceDraft,GovernanceRelease,RMCapacity,CustomerCoverage,ChatSession,SessionTurn])

from .banking import BANKING_TABLES  # noqa: E402,F401  registers bank/POI tables on Base.metadata
