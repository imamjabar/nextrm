"""Add enrichment records. No existing rows or columns are changed."""
from alembic import op
import sqlalchemy as sa
revision='0007_engagement_enrichment'
down_revision='0006_engagement_nudges'
branch_labels=None
depends_on=None

def upgrade():
    # Frozen DDL: do not import current application metadata into this migration.
    tables={
      'rm_engagement_profiles':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('data_json',sa.Text(),nullable=False),sa.Column('updated_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id','party_id')],
      'rm_suggestion_meta':[sa.Column('id',sa.String(80),sa.ForeignKey('rm_nudges.id'),primary_key=True),sa.Column('family',sa.String(8),nullable=False),sa.Column('topic',sa.String(40),nullable=False),sa.Column('category',sa.String(30),nullable=False),sa.Column('dependencies_json',sa.Text(),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False)],
      'rm_engagement_decisions':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('digest',sa.String(64),nullable=False),sa.Column('data_json',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id','party_id','digest')],
      'rm_engagement_feedback':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('nudge_id',sa.String(80),sa.ForeignKey('rm_nudges.id')),sa.Column('action',sa.String(30),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),sa.Column('result_json',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('tenant_id','party_id','request_key')],
      'rm_followup_details':[sa.Column('id',sa.String(80),sa.ForeignKey('rm_journeys.id'),primary_key=True),sa.Column('snoozed_until',sa.DateTime()),sa.Column('outcome',sa.String(40))],
      'rm_contact_records':[sa.Column('id',sa.String(80),primary_key=True),sa.Column('party_id',sa.String(80),sa.ForeignKey('rm_parties.id'),nullable=False),sa.Column('actor_id',sa.String(80),nullable=False),sa.Column('channel',sa.String(20),nullable=False),sa.Column('purpose',sa.String(30),nullable=False),sa.Column('event',sa.String(30),nullable=False),sa.Column('note',sa.Text(),nullable=False),sa.Column('source_id',sa.String(100),sa.ForeignKey('rm_sources.id'),nullable=False),sa.Column('occurred_at',sa.DateTime(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),sa.UniqueConstraint('tenant_id','actor_id','request_key')]
    }
    for name,columns in tables.items():
        if not sa.inspect(op.get_bind()).has_table(name):
            op.create_table(name,sa.Column('tenant_id',sa.String(50),sa.ForeignKey('institutions.id'),nullable=False),*columns)
            op.create_index('ix_'+name+'_tenant_id',name,['tenant_id'])

def downgrade():
    raise RuntimeError('Preserve relationship evidence and feedback; roll forward or restore a reviewed backup.')
