"""Create fresh schema or adopt a compatible legacy schema; additive tables only.

Legacy snapshots/approvals are not rewritten into claimed verified decisions.
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_guarded_schema'
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()

institutions = sa.Table(
    'institutions', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('name', sa.String(100), nullable=False),
    sa.Column('institution_type', sa.String(20), nullable=False),
    sa.Column('policy_pack_id', sa.String(50), server_default="default-policy"),
    sa.Column('policy_version', sa.String(20), server_default="1.0.0"),
    sa.Column('approval_mode', sa.String(30), server_default="SANDBOX_LOCAL"),
    sa.Column('created_at', sa.DateTime),
)

user_assignments = sa.Table(
    'user_assignments', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('user_id', sa.String(50), nullable=False),
    sa.Column('name', sa.String(100), nullable=False),
    sa.Column('email', sa.String(100), nullable=False),
    sa.Column('role', sa.String(30), nullable=False),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('entity_id', sa.String(50), nullable=True),
    sa.Column('active', sa.Boolean, server_default=sa.true()),
)

business_entities = sa.Table(
    'business_entities', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('name', sa.String(200), nullable=False),
    sa.Column('registration_number', sa.String(100), nullable=True),
    sa.Column('tax_id', sa.String(50), nullable=True),
    sa.Column('sector', sa.String(100), nullable=False),
    sa.Column('subsector', sa.String(100), nullable=True),
    sa.Column('address', sa.String(300), nullable=False),
    sa.Column('city', sa.String(100), nullable=False),
    sa.Column('province', sa.String(100), nullable=False),
)

relationships = sa.Table(
    'relationships', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('entity_id', sa.String(50), sa.ForeignKey("business_entities.id"), nullable=False),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('state', sa.String(50), nullable=False),
    sa.Column('crm_customer_id', sa.String(50), nullable=True),
    sa.Column('verified_at', sa.DateTime, nullable=True),
)

opportunities = sa.Table(
    'opportunities', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('channel', sa.String(30), nullable=False),
    sa.Column('entity_id', sa.String(50), sa.ForeignKey("business_entities.id"), nullable=True),
    sa.Column('company_name', sa.String(200), nullable=False),
    sa.Column('owner_id', sa.String(50), nullable=False),
    sa.Column('owner_name', sa.String(100), nullable=False),
    sa.Column('lifecycle', sa.String(30), nullable=False),
    sa.Column('identity_state', sa.String(30), nullable=False),
    sa.Column('relationship_state', sa.String(30), nullable=False),
    sa.Column('contact_eligibility', sa.String(30), nullable=False),
    sa.Column('priority_reasons_json', sa.Text, nullable=False),
    sa.Column('need_hypothesis', sa.Text, nullable=True),
    sa.Column('next_question', sa.Text, nullable=True),
    sa.Column('crm_reference', sa.String(100), nullable=True),
    sa.Column('source_description', sa.String(300), nullable=False),
    sa.Column('source_date', sa.Date, nullable=False),
    sa.Column('created_at', sa.DateTime),
    sa.Column('version', sa.Integer, server_default='1'),
)

need_records = sa.Table(
    'need_records', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('opportunity_id', sa.String(50), sa.ForeignKey("opportunities.id"), nullable=False),
    sa.Column('purpose', sa.String(300), nullable=False),
    sa.Column('inventory_payment', sa.Numeric(18, 2), nullable=False),
    sa.Column('own_contribution', sa.Numeric(18, 2), nullable=False),
    sa.Column('simple_order_gap', sa.Numeric(18, 2), nullable=False),
    sa.Column('expected_collection_date', sa.Date, nullable=False),
    sa.Column('reviewed', sa.Boolean, server_default=sa.false()),
    sa.Column('reviewed_by', sa.String(50), nullable=True),
    sa.Column('reviewed_at', sa.DateTime, nullable=True),
    sa.Column('unverified_fields_json', sa.Text, server_default='[]'),
    sa.Column('version', sa.Integer, server_default='1'),
    sa.Column('created_at', sa.DateTime),
)

financing_cases = sa.Table(
    'financing_cases', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('borrower_entity_id', sa.String(50), sa.ForeignKey("business_entities.id"), nullable=False),
    sa.Column('borrower_name', sa.String(200), nullable=False),
    sa.Column('opportunity_id', sa.String(50), sa.ForeignKey("opportunities.id"), nullable=True),
    sa.Column('profile', sa.String(30), nullable=False),
    sa.Column('requested_purpose', sa.String(300), nullable=False),
    sa.Column('lifecycle', sa.String(30), nullable=False),
    sa.Column('active_version', sa.Integer, server_default='3'),
    sa.Column('rm_id', sa.String(50), nullable=False),
    sa.Column('analyst_id', sa.String(50), nullable=True),
    sa.Column('approver_id', sa.String(50), nullable=True),
    sa.Column('created_at', sa.DateTime),
    sa.Column('updated_at', sa.DateTime),
)

case_snapshots = sa.Table(
    'case_snapshots', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('version', sa.Integer, nullable=False),
    sa.Column('snapshot_hash', sa.String(64), nullable=False),
    sa.Column('facts_json', sa.Text, nullable=False),
    sa.Column('snapshot_data_json', sa.Text, nullable=False),
    sa.Column('created_at', sa.DateTime),
    sa.Column('created_by', sa.String(50), nullable=False),
)

evidence = sa.Table(
    'evidence', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('title', sa.String(200), nullable=False),
    sa.Column('file_name', sa.String(200), nullable=False),
    sa.Column('file_type', sa.String(50), nullable=False),
    sa.Column('file_hash', sa.String(64), nullable=False),
    sa.Column('uploaded_by', sa.String(100), nullable=False),
    sa.Column('uploaded_at', sa.DateTime),
)

recommendations = sa.Table(
    'recommendations', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('base_case_version', sa.Integer, nullable=False),
    sa.Column('kind', sa.String(30), nullable=False),
    sa.Column('field_name', sa.String(100), nullable=False),
    sa.Column('previous_value', sa.String(200), nullable=True),
    sa.Column('proposed_value', sa.String(200), nullable=False),
    sa.Column('explanation', sa.Text, nullable=False),
    sa.Column('business_consequence', sa.Text, nullable=False),
    sa.Column('evidence_refs_json', sa.Text, nullable=False),
    sa.Column('review_status', sa.String(30), nullable=False),
    sa.Column('reviewer_notes', sa.Text, nullable=True),
    sa.Column('required_reviewer_role', sa.String(30), nullable=False),
    sa.Column('created_at', sa.DateTime),
    sa.Column('resolved_at', sa.DateTime, nullable=True),
)

approvals = sa.Table(
    'approvals', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('case_version', sa.Integer, nullable=False),
    sa.Column('decision', sa.String(30), nullable=False),
    sa.Column('source_mode', sa.String(30), nullable=False),
    sa.Column('approved_terms_json', sa.Text, nullable=False),
    sa.Column('conditions_json', sa.Text, nullable=False),
    sa.Column('external_reference', sa.String(100), nullable=True),
    sa.Column('external_decision_at', sa.DateTime, nullable=True),
    sa.Column('external_proof_digest', sa.String(64), nullable=True),
    sa.Column('actor_id', sa.String(50), nullable=False),
    sa.Column('actor_name', sa.String(100), nullable=False),
    sa.Column('actor_role', sa.String(30), nullable=False),
    sa.Column('comments', sa.Text, nullable=True),
    sa.Column('created_at', sa.DateTime),
)

execution_operations = sa.Table(
    'execution_operations', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('case_version', sa.Integer, nullable=False),
    sa.Column('operation_type', sa.String(30), nullable=False),
    sa.Column('idempotency_key', sa.String(100), nullable=False),
    sa.Column('amount', sa.Numeric(18, 2), nullable=False),
    sa.Column('payee_name', sa.String(200), nullable=False),
    sa.Column('payee_account', sa.String(100), nullable=False),
    sa.Column('status', sa.String(30), nullable=False),
    sa.Column('funding_status', sa.String(30), nullable=False),
    sa.Column('delivery_status', sa.String(30), nullable=False),
    sa.Column('requested_by', sa.String(50), nullable=False),
    sa.Column('requested_at', sa.DateTime),
    sa.Column('completed_at', sa.DateTime, nullable=True),
    sa.Column('error_message', sa.Text, nullable=True),
    sa.Column('execution_meta_json', sa.Text, nullable=False),
    sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency_key"),
)

audit_events = sa.Table(
    'audit_events', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('actor_id', sa.String(50), nullable=False),
    sa.Column('actor_name', sa.String(100), nullable=False),
    sa.Column('actor_role', sa.String(30), nullable=False),
    sa.Column('action', sa.String(50), nullable=False),
    sa.Column('resource_type', sa.String(50), nullable=False),
    sa.Column('resource_id', sa.String(50), nullable=False),
    sa.Column('correlation_id', sa.String(50), nullable=False),
    sa.Column('details_json', sa.Text, nullable=False),
    sa.Column('created_at', sa.DateTime),
)

case_states = sa.Table(
    'case_states', metadata,
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), primary_key=True),
    sa.Column('facts_json', sa.Text, nullable=False),
)

approval_bindings = sa.Table(
    'approval_bindings', metadata,
    sa.Column('approval_id', sa.String(50), sa.ForeignKey("approvals.id"), primary_key=True),
    sa.Column('snapshot_hash', sa.String(64), nullable=False),
)

approval_conditions = sa.Table(
    'approval_conditions', metadata,
    sa.Column('id', sa.String(100), primary_key=True),
    sa.Column('approval_id', sa.String(50), sa.ForeignKey("approvals.id"), nullable=False),
    sa.Column('condition_type', sa.String(50), nullable=False),
    sa.Column('description', sa.Text, nullable=False),
    sa.Column('status', sa.String(30), nullable=False),
    sa.Column('verified_by', sa.String(100), nullable=True),
    sa.Column('verified_at', sa.DateTime, nullable=True),
    sa.Column('comments', sa.Text, nullable=True),
)

opportunity_case_links = sa.Table(
    'opportunity_case_links', metadata,
    sa.Column('id', sa.String(50), primary_key=True),
    sa.Column('tenant_id', sa.String(50), sa.ForeignKey("institutions.id"), nullable=False),
    sa.Column('opportunity_id', sa.String(50), sa.ForeignKey("opportunities.id"), nullable=False),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('idempotency_key', sa.String(100), nullable=False),
    sa.Column('created_at', sa.DateTime),
    sa.UniqueConstraint("tenant_id", "idempotency_key"),
)

profile_gates = sa.Table(
    'profile_gates', metadata,
    sa.Column('id', sa.String(100), primary_key=True),
    sa.Column('case_id', sa.String(50), sa.ForeignKey("financing_cases.id"), nullable=False),
    sa.Column('gate', sa.String(50), nullable=False),
    sa.Column('satisfied', sa.Boolean, server_default=sa.false(), nullable=False),
    sa.Column('evidence_reference', sa.Text, nullable=True),
    sa.Column('amount', sa.Numeric(18, 2), nullable=True),
    sa.Column('valid_until', sa.DateTime, nullable=True),
    sa.Column('verified_by', sa.String(50), nullable=True),
    sa.UniqueConstraint("case_id", "gate"),
)

def upgrade():
    bind = op.get_bind()
    existing = sa.inspect(bind)
    for table in metadata.sorted_tables:
        if existing.has_table(table.name):
            present = {c['name'] for c in existing.get_columns(table.name)}
            missing = set(table.columns.keys()) - present
            if missing:
                raise RuntimeError(f'Legacy table {table.name} lacks {sorted(missing)}. Stop and prepare an explicit data migration; no automatic backfill is safe.')
    metadata.create_all(bind, checkfirst=True)

def downgrade():
    raise RuntimeError('Automatic destructive downgrade is disabled. Restore the tested database backup or roll forward.')
