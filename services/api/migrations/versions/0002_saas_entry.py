"""Additive POC access and demo inquiry records. No existing data is rewritten."""
from alembic import op
import sqlalchemy as sa

revision = '0002_saas_entry'
down_revision = '0001_guarded_schema'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table('institution_access'):
        op.create_table(
            'institution_access',
            sa.Column('tenant_id', sa.String(50), sa.ForeignKey('institutions.id'), primary_key=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('data_mode', sa.String(20), nullable=False, server_default='SYNTHETIC'),
        )
    if not insp.has_table('demo_requests'):
        op.create_table(
            'demo_requests',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('payload_hash', sa.String(64), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('email', sa.String(254), nullable=False),
            sa.Column('institution', sa.String(150), nullable=False),
            sa.Column('institution_type', sa.String(20), nullable=False),
            sa.Column('needs', sa.String(2000), nullable=False, server_default=''),
            sa.Column('status', sa.String(20), nullable=False, server_default='NEW'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
    if not insp.has_table('inquiry_rate_slots'):
        op.create_table(
            'inquiry_rate_slots',
            sa.Column('id', sa.String(150), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

def downgrade():
    raise RuntimeError('Preserve inquiry/access records; roll forward or restore a verified backup.')
