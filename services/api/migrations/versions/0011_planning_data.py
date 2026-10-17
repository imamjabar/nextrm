"""Add account terms, investment holdings and savings goals for planning insights. Additive only."""
from alembic import op
import sqlalchemy as sa
revision = '0011_planning_data'
down_revision = '0010_bank_data_poi'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {x['name'] for x in sa.inspect(bind).get_columns('bank_accounts')}
    for name, kind in (('interest_rate_percent', sa.Numeric(6, 2)), ('minimum_payment', sa.Numeric(18, 2)), ('payment_due_day', sa.Integer())):
        if name not in columns:
            op.add_column('bank_accounts', sa.Column(name, kind, nullable=True))
    tenant = lambda: sa.Column('tenant_id', sa.String(50), sa.ForeignKey('institutions.id'), nullable=False)
    customer = lambda: sa.Column('customer_id', sa.String(80), sa.ForeignKey('bank_customers.id'), nullable=False)
    tables = {
        'bank_holdings': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(), customer(),
            sa.Column('instrument', sa.String(120), nullable=False), sa.Column('asset_class', sa.String(20), nullable=False),
            sa.Column('cost_basis', sa.Numeric(18, 2), nullable=False), sa.Column('market_value', sa.Numeric(18, 2), nullable=False),
            sa.Column('value_30d_ago', sa.Numeric(18, 2)), sa.Column('as_of', sa.DateTime(), nullable=False),
            sa.Column('mode', sa.String(20), nullable=False, server_default='SYNTHETIC')],
        'bank_goals': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(), customer(),
            sa.Column('name', sa.String(120), nullable=False), sa.Column('target_amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('saved_amount', sa.Numeric(18, 2), nullable=False), sa.Column('monthly_plan', sa.Numeric(18, 2), nullable=False),
            sa.Column('target_date', sa.Date(), nullable=False), sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
            sa.Column('mode', sa.String(20), nullable=False, server_default='SYNTHETIC')],
    }
    for name, cols in tables.items():
        if not sa.inspect(bind).has_table(name):
            op.create_table(name, *cols)
        existing = {x['name'] for x in sa.inspect(bind).get_indexes(name)}
        for index, column in ((f'ix_{name}_tenant_id', 'tenant_id'), (f'ix_{name}_customer_id', 'customer_id')):
            if index not in existing:
                op.create_index(index, name, [column])


def downgrade():
    raise RuntimeError('Retain banking records. Use a reviewed backup or roll forward.')
