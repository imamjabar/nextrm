"""Add core-banking customer/account/transaction records and points of interest. Additive only."""
from alembic import op
import sqlalchemy as sa
revision = '0010_bank_data_poi'
down_revision = '0009_governance_sessions'
branch_labels = None
depends_on = None


def upgrade():
    tenant = lambda: sa.Column('tenant_id', sa.String(50), sa.ForeignKey('institutions.id'), nullable=False)
    tables = {
        'bank_customers': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(),
            sa.Column('cif', sa.String(30), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
            sa.Column('full_name', sa.String(180), nullable=False), sa.Column('normalized_name', sa.String(180), nullable=False),
            sa.Column('nik_hash', sa.String(64)), sa.Column('npwp_hash', sa.String(64)), sa.Column('phone_hash', sa.String(64)),
            sa.Column('email_hash', sa.String(64)), sa.Column('phone_masked', sa.String(24)),
            sa.Column('address', sa.String(240), nullable=False), sa.Column('city', sa.String(80), nullable=False),
            sa.Column('latitude', sa.Numeric(10, 6)), sa.Column('longitude', sa.Numeric(10, 6)),
            sa.Column('segment', sa.String(40), nullable=False), sa.Column('opened_at', sa.Date(), nullable=False),
            sa.Column('party_id', sa.String(80), sa.ForeignKey('rm_parties.id')),
            sa.Column('mode', sa.String(20), nullable=False, server_default='SYNTHETIC'),
            sa.UniqueConstraint('tenant_id', 'cif')],
        'bank_accounts': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(),
            sa.Column('customer_id', sa.String(80), sa.ForeignKey('bank_customers.id'), nullable=False),
            sa.Column('account_masked', sa.String(24), nullable=False), sa.Column('product', sa.String(30), nullable=False),
            sa.Column('currency', sa.String(3), nullable=False, server_default='IDR'),
            sa.Column('balance', sa.Numeric(18, 2), nullable=False), sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
            sa.Column('opened_at', sa.Date(), nullable=False), sa.Column('maturity_date', sa.Date())],
        'bank_transactions': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(),
            sa.Column('account_id', sa.String(80), sa.ForeignKey('bank_accounts.id'), nullable=False),
            sa.Column('customer_id', sa.String(80), sa.ForeignKey('bank_customers.id'), nullable=False),
            sa.Column('posted_at', sa.DateTime(), nullable=False), sa.Column('amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('direction', sa.String(6), nullable=False), sa.Column('category', sa.String(40), nullable=False),
            sa.Column('merchant', sa.String(120), nullable=False), sa.Column('description', sa.String(200), nullable=False),
            sa.Column('channel', sa.String(20), nullable=False)],
        'poi_places': [
            sa.Column('id', sa.String(80), primary_key=True), tenant(),
            sa.Column('provider', sa.String(30), nullable=False), sa.Column('provider_place_id', sa.String(200), nullable=False),
            sa.Column('name', sa.String(180), nullable=False), sa.Column('primary_type', sa.String(60), nullable=False),
            sa.Column('address', sa.String(240), nullable=False),
            sa.Column('latitude', sa.Numeric(10, 6), nullable=False), sa.Column('longitude', sa.Numeric(10, 6), nullable=False),
            sa.Column('phone_hash', sa.String(64)), sa.Column('phone_masked', sa.String(24)), sa.Column('website', sa.String(240)),
            sa.Column('rating', sa.Numeric(2, 1)), sa.Column('rating_count', sa.Integer()),
            sa.Column('attribution', sa.String(200), nullable=False),
            sa.Column('fetched_at', sa.DateTime(), nullable=False), sa.Column('expires_at', sa.DateTime()),
            sa.Column('match_status', sa.String(40), nullable=False, server_default='UNREVIEWED'),
            sa.Column('matched_customer_id', sa.String(80), sa.ForeignKey('bank_customers.id')),
            sa.Column('match_score', sa.Numeric(4, 3)), sa.Column('match_reasons_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('matched_at', sa.DateTime()), sa.Column('prospect_id', sa.String(80), sa.ForeignKey('rm_prospects.id')),
            sa.UniqueConstraint('tenant_id', 'provider', 'provider_place_id')],
    }
    indexes = {
        'bank_customers': [('ix_bank_customers_tenant_id', ['tenant_id']), ('ix_bank_customer_name', ['tenant_id', 'normalized_name']),
                           ('ix_bank_customer_phone', ['tenant_id', 'phone_hash']), ('ix_bank_customer_npwp', ['tenant_id', 'npwp_hash']),
                           ('ix_bank_customer_email', ['tenant_id', 'email_hash'])],
        'bank_accounts': [('ix_bank_accounts_tenant_id', ['tenant_id']), ('ix_bank_accounts_customer_id', ['customer_id'])],
        'bank_transactions': [('ix_bank_transactions_tenant_id', ['tenant_id']), ('ix_bank_txn_customer_time', ['tenant_id', 'customer_id', 'posted_at'])],
        'poi_places': [('ix_poi_places_tenant_id', ['tenant_id']), ('ix_poi_tenant_geo', ['tenant_id', 'latitude', 'longitude'])],
    }
    bind = op.get_bind()
    for name, cols in tables.items():
        if not sa.inspect(bind).has_table(name):
            op.create_table(name, *cols)
        existing = {x['name'] for x in sa.inspect(bind).get_indexes(name)}
        for index, columns in indexes[name]:
            if index not in existing:
                op.create_index(index, name, columns)


def downgrade():
    raise RuntimeError('Retain banking and POI records. Use a reviewed backup or roll forward.')
