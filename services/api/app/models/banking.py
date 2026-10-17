"""Core-banking customer records (synthetic in the demo) and points of interest for acquisition.

Personal identifiers are never stored in clear: matching uses SHA-256 hashes of normalized values
(see services/customer_match.py) and the UI only shows masked suffixes.
"""
from sqlalchemy import Column, String, Text, Integer, Date, DateTime, Numeric, ForeignKey, Index, UniqueConstraint
from ..core.database import Base
from .entities import utc_now


class BankCustomer(Base):
    __tablename__ = 'bank_customers'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    cif = Column(String(30), nullable=False)
    kind = Column(String(20), nullable=False)  # PERSON | ORGANIZATION
    full_name = Column(String(180), nullable=False)
    normalized_name = Column(String(180), nullable=False)
    nik_hash = Column(String(64), nullable=True)
    npwp_hash = Column(String(64), nullable=True)
    phone_hash = Column(String(64), nullable=True)
    email_hash = Column(String(64), nullable=True)
    phone_masked = Column(String(24), nullable=True)
    address = Column(String(240), nullable=False)
    city = Column(String(80), nullable=False)
    latitude = Column(Numeric(10, 6), nullable=True)
    longitude = Column(Numeric(10, 6), nullable=True)
    segment = Column(String(40), nullable=False)  # MASS | AFFLUENT | SME | CORPORATE
    opened_at = Column(Date, nullable=False)
    party_id = Column(String(80), ForeignKey('rm_parties.id'), nullable=True)
    mode = Column(String(20), nullable=False, default='SYNTHETIC')
    __table_args__ = (
        UniqueConstraint('tenant_id', 'cif'),
        Index('ix_bank_customer_name', 'tenant_id', 'normalized_name'),
        Index('ix_bank_customer_phone', 'tenant_id', 'phone_hash'),
        Index('ix_bank_customer_npwp', 'tenant_id', 'npwp_hash'),
        Index('ix_bank_customer_email', 'tenant_id', 'email_hash'),
    )


class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    customer_id = Column(String(80), ForeignKey('bank_customers.id'), nullable=False, index=True)
    account_masked = Column(String(24), nullable=False)
    product = Column(String(30), nullable=False)  # SAVINGS | CURRENT | TERM_DEPOSIT | CREDIT_CARD
    currency = Column(String(3), nullable=False, default='IDR')
    balance = Column(Numeric(18, 2), nullable=False)
    status = Column(String(20), nullable=False, default='ACTIVE')
    opened_at = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=True)
    interest_rate_percent = Column(Numeric(6, 2), nullable=True)  # contractual annual rate; NULL when not recorded
    minimum_payment = Column(Numeric(18, 2), nullable=True)  # CREDIT_CARD only
    payment_due_day = Column(Integer, nullable=True)  # CREDIT_CARD only


class BankTransaction(Base):
    __tablename__ = 'bank_transactions'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    account_id = Column(String(80), ForeignKey('bank_accounts.id'), nullable=False)
    customer_id = Column(String(80), ForeignKey('bank_customers.id'), nullable=False)
    posted_at = Column(DateTime, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)  # always positive; direction carries the sign
    direction = Column(String(6), nullable=False)  # CREDIT | DEBIT
    category = Column(String(40), nullable=False)
    merchant = Column(String(120), nullable=False)
    description = Column(String(200), nullable=False)
    channel = Column(String(20), nullable=False)
    __table_args__ = (Index('ix_bank_txn_customer_time', 'tenant_id', 'customer_id', 'posted_at'),)


class PoiPlace(Base):
    __tablename__ = 'poi_places'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    provider = Column(String(30), nullable=False)  # GOOGLE_PLACES | SYNTHETIC_DATASET
    provider_place_id = Column(String(200), nullable=False)
    name = Column(String(180), nullable=False)
    primary_type = Column(String(60), nullable=False)
    address = Column(String(240), nullable=False)
    latitude = Column(Numeric(10, 6), nullable=False)
    longitude = Column(Numeric(10, 6), nullable=False)
    phone_hash = Column(String(64), nullable=True)
    phone_masked = Column(String(24), nullable=True)
    website = Column(String(240), nullable=True)
    rating = Column(Numeric(2, 1), nullable=True)
    rating_count = Column(Integer, nullable=True)
    attribution = Column(String(200), nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=True)  # provider content retention limit; NULL for owned synthetic data
    match_status = Column(String(40), nullable=False, default='UNREVIEWED')  # EXISTING_CUSTOMER | POSSIBLE_MATCH | NO_MATCH_IN_AVAILABLE_DATA | UNREVIEWED
    matched_customer_id = Column(String(80), ForeignKey('bank_customers.id'), nullable=True)
    match_score = Column(Numeric(4, 3), nullable=True)
    match_reasons_json = Column(Text, nullable=False, default='[]')
    matched_at = Column(DateTime, nullable=True)
    prospect_id = Column(String(80), ForeignKey('rm_prospects.id'), nullable=True)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'provider', 'provider_place_id'),
        Index('ix_poi_tenant_geo', 'tenant_id', 'latitude', 'longitude'),
    )


class BankHolding(Base):
    __tablename__ = 'bank_holdings'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    customer_id = Column(String(80), ForeignKey('bank_customers.id'), nullable=False, index=True)
    instrument = Column(String(120), nullable=False)
    asset_class = Column(String(20), nullable=False)  # MONEY_MARKET | BOND | EQUITY
    cost_basis = Column(Numeric(18, 2), nullable=False)
    market_value = Column(Numeric(18, 2), nullable=False)
    value_30d_ago = Column(Numeric(18, 2), nullable=True)  # NULL when no history is available
    as_of = Column(DateTime, nullable=False)
    mode = Column(String(20), nullable=False, default='SYNTHETIC')


class BankGoal(Base):
    __tablename__ = 'bank_goals'
    id = Column(String(80), primary_key=True)
    tenant_id = Column(String(50), ForeignKey('institutions.id'), nullable=False, index=True)
    customer_id = Column(String(80), ForeignKey('bank_customers.id'), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    target_amount = Column(Numeric(18, 2), nullable=False)
    saved_amount = Column(Numeric(18, 2), nullable=False)
    monthly_plan = Column(Numeric(18, 2), nullable=False)
    target_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default='ACTIVE')
    mode = Column(String(20), nullable=False, default='SYNTHETIC')


BANKING_TABLES = [BankCustomer, BankAccount, BankTransaction, PoiPlace, BankHolding, BankGoal]
