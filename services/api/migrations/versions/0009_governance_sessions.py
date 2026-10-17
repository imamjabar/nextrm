"""Add versioned governance, coverage and session adapters. Preserve old conversations."""
from alembic import op
import sqlalchemy as sa
revision='0009_governance_sessions'
down_revision='0008_customer_activity'
branch_labels=None
depends_on=None

def upgrade():
    columns={
      'rm_governance_drafts':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('version',sa.Integer(),nullable=False),sa.Column('definition_json',sa.Text(),nullable=False),sa.Column('tested_digest',sa.String(64)),sa.Column('test_json',sa.Text(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id')],
      'rm_governance_releases':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('version',sa.Integer(),nullable=False),sa.Column('definition_json',sa.Text(),nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('actor_id',sa.String(80),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id','version'),sa.UniqueConstraint('tenant_id','request_key')],
      'rm_capacity':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('user_id',sa.String(80),nullable=False),sa.Column('dedicated_limit',sa.Integer(),nullable=False),sa.Column('case_limit',sa.Integer(),nullable=False),sa.Column('pool_enabled',sa.Boolean(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.UniqueConstraint('tenant_id','user_id')],
      'rm_customer_coverage':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('mode',sa.String(20),nullable=False),sa.Column('rm_id',sa.String(80)),sa.Column('pool_id',sa.String(80),nullable=False),sa.Column('tier',sa.String(30),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.UniqueConstraint('tenant_id','party_id')],
      'rm_chat_sessions':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('actor_id',sa.String(80),nullable=False),sa.Column('title',sa.String(120),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),sa.Column('archived',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id','actor_id','request_key')],
      'rm_session_turns':[sa.Column('id',sa.String(80),sa.ForeignKey('rm_turns.id'),primary_key=True),sa.Column('session_id',sa.String(80),sa.ForeignKey('rm_chat_sessions.id'),nullable=False)]}
    for name,cols in columns.items():
        if not sa.inspect(op.get_bind()).has_table(name):
            op.create_table(name,sa.Column('tenant_id',sa.String(50),sa.ForeignKey('institutions.id'),nullable=False),*cols)
            op.create_index('ix_'+name+'_tenant_id',name,['tenant_id'])
    existing={x['name'] for x in sa.inspect(op.get_bind()).get_indexes('rm_chat_sessions')}
    if 'ix_rm_session_subject_time' not in existing:op.create_index('ix_rm_session_subject_time','rm_chat_sessions',['tenant_id','party_id','actor_id','updated_at','id'])
    existing={x['name'] for x in sa.inspect(op.get_bind()).get_indexes('rm_session_turns')}
    if 'ix_rm_session_turns_session_id' not in existing:op.create_index('ix_rm_session_turns_session_id','rm_session_turns',['session_id'])

def downgrade():raise RuntimeError('Retain governance/session/assignment evidence. Use a reviewed backup or roll forward.')
