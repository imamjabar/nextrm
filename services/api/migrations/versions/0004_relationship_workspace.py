"""Add the tenant-owned person/business relationship workspace; preserve credit tables."""
from alembic import op
revision='0004_relationship_workspace'
down_revision='0003_local_demo_accounts'
branch_labels=None
depends_on=None

def upgrade():
    from app.models.relationships import RM_TABLES
    for model in RM_TABLES: model.__table__.create(bind=op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('Destructive automatic downgrade disabled; restore a reviewed backup or roll forward.')
