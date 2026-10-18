"""Add contact preferences for RM requests. Additive only."""
from alembic import op
import sqlalchemy as sa

revision = '0012_contact_preferences'
down_revision = '0011_planning_data'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    name = 'rm_contact_preferences'
    if not sa.inspect(bind).has_table(name):
        op.create_table(
            name,
            sa.Column('id', sa.String(80), primary_key=True),
            sa.Column('tenant_id', sa.String(50), sa.ForeignKey('institutions.id'), nullable=False),
            sa.Column('party_id', sa.String(80), sa.ForeignKey('rm_parties.id'), nullable=False),
            sa.Column('signal_id', sa.String(80), sa.ForeignKey('rm_signals.id'), nullable=False),
            sa.Column('actor_id', sa.String(80), nullable=False),
            sa.Column('method', sa.String(20), nullable=False),
            sa.Column('window', sa.String(20), nullable=False),
            sa.Column('request_key', sa.String(100), nullable=False),
            sa.Column('payload_hash', sa.String(64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('tenant_id', 'actor_id', 'request_key'),
        )
    existing = {x['name'] for x in sa.inspect(bind).get_indexes(name)}
    if f'ix_{name}_tenant_id' not in existing:
        op.create_index(f'ix_{name}_tenant_id', name, ['tenant_id'])
    if 'ix_rm_contact_pref_signal' not in existing:
        op.create_index('ix_rm_contact_pref_signal', name, ['tenant_id', 'signal_id', 'created_at'])

def downgrade():
    raise RuntimeError('Retain contact preference records. Use a reviewed backup or roll forward.')
