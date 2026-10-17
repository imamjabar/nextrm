"""Persist observed app activity without altering financial or relationship states."""
from alembic import op
import sqlalchemy as sa
revision='0008_customer_activity'
down_revision='0007_engagement_enrichment'
branch_labels=None
depends_on=None

def upgrade():
    if sa.inspect(op.get_bind()).has_table('rm_app_activity'):return
    op.create_table('rm_app_activity',
        sa.Column('id',sa.String(80),primary_key=True),
        sa.Column('tenant_id',sa.String(50),sa.ForeignKey('institutions.id'),nullable=False),
        sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),
        sa.Column('actor_id',sa.String(80),nullable=False),sa.Column('kind',sa.String(40),nullable=False),
        sa.Column('product',sa.String(20),nullable=False),sa.Column('origin',sa.String(40),nullable=False),
        sa.Column('occurred_at',sa.DateTime(),nullable=False),sa.Column('ingested_at',sa.DateTime(),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),
        sa.Column('mode',sa.String(20),nullable=False),sa.Column('source_id',sa.String(100),sa.ForeignKey('rm_sources.id'),nullable=False),
        sa.Column('signal_id',sa.String(80),sa.ForeignKey('rm_signals.id'),nullable=True),
        sa.UniqueConstraint('tenant_id','party_id','request_key'))
    op.create_index('ix_rm_app_activity_tenant_id','rm_app_activity',['tenant_id'])
    op.create_index('ix_rm_app_activity_party_id','rm_app_activity',['party_id'])

def downgrade():raise RuntimeError('Retain app activity evidence; roll forward or restore a reviewed backup.')
