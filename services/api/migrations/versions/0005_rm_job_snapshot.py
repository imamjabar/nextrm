"""Pin evaluation input/configuration and safely complete earlier local prototype metadata."""
from alembic import op
import sqlalchemy as sa
revision='0005_rm_job_snapshot'
down_revision='0004_relationship_workspace'
branch_labels=None
depends_on=None

def upgrade():
    columns={x['name'] for x in sa.inspect(op.get_bind()).get_columns('rm_evaluation_runs')}
    if 'config_json' not in columns:op.add_column('rm_evaluation_runs',sa.Column('config_json',sa.Text(),nullable=False,server_default='{}'))

def downgrade():raise RuntimeError('Use reviewed roll-forward or backup restoration; automatic destructive downgrade disabled.')
