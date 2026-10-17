from alembic import op
import sqlalchemy as sa

revision = '0003_local_demo_accounts'
down_revision = '0002_saas_entry'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table('local_accounts'):
        op.create_table(
            'local_accounts',
            sa.Column('id', sa.String(50), primary_key=True),
            sa.Column('email', sa.String(254), unique=True, nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('password_hash', sa.String(300), nullable=False),
            sa.Column('platform_admin', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if not insp.has_table('local_sessions'):
        op.create_table(
            'local_sessions',
            sa.Column('token_hash', sa.String(64), primary_key=True),
            sa.Column('user_id', sa.String(50), sa.ForeignKey('local_accounts.id'), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        )

def downgrade():
    raise RuntimeError('Preserve accounts. Roll forward or restore a backup.')
