"""Add persistent, sourced in-app suggestions without altering existing records."""
from alembic import op
import sqlalchemy as sa

revision='0006_engagement_nudges'
down_revision='0005_rm_job_snapshot'
branch_labels=None
depends_on=None

def upgrade():
    if sa.inspect(op.get_bind()).has_table('rm_nudges'):
        return
    op.create_table('rm_nudges',
        sa.Column('id',sa.String(80),primary_key=True),
        sa.Column('tenant_id',sa.String(50),sa.ForeignKey('institutions.id'),nullable=False),
        sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),
        sa.Column('source_id',sa.String(100),sa.ForeignKey('rm_sources.id'),nullable=False),
        sa.Column('knowledge_id',sa.String(100),sa.ForeignKey('rm_sources.id'),nullable=False),
        sa.Column('route',sa.String(30),nullable=False),
        sa.Column('title',sa.String(180),nullable=False),
        sa.Column('body',sa.Text(),nullable=False),
        sa.Column('prompt',sa.Text(),nullable=False),
        sa.Column('state',sa.String(30),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('signal_id',sa.String(80),sa.ForeignKey('rm_signals.id'),nullable=True),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_rm_nudges_tenant_id','rm_nudges',['tenant_id'])
    op.create_index('ix_rm_nudges_party_id','rm_nudges',['party_id'])

def downgrade():
    raise RuntimeError('Retain engagement history; use a reviewed backup or roll forward.')
