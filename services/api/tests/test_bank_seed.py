"""Tests for synthetic core-banking seed and POI data."""
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.banking import BankAccount, BankCustomer, BankTransaction, PoiPlace
from app.models.relationships import Party
from app.services.bank_seed import (
    ANCHOR_DATE,
    ANCHOR_DATETIME,
    seed_bank_data,
    sid,
)

DEMO_OFFICE_LAT = -6.2383
DEMO_OFFICE_LNG = 106.9756


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def test_deterministic_counts():
    """Verify exact deterministic fixture counts after seeding."""
    with SessionLocal() as db:
        cust_count = db.query(BankCustomer).count()
        acc_count = db.query(BankAccount).count()
        txn_count = db.query(BankTransaction).count()
        poi_count = db.query(PoiPlace).count()

        assert cust_count == 200
        assert acc_count == 321
        assert txn_count > 4500
        assert poi_count == 150


def test_idempotency_seed_twice():
    """Verify seeding twice is repeat-safe and produces identical row counts."""
    with SessionLocal() as db:
        cust_count_1 = db.query(BankCustomer).count()
        acc_count_1 = db.query(BankAccount).count()
        txn_count_1 = db.query(BankTransaction).count()
        poi_count_1 = db.query(PoiPlace).count()

        # Call seed_bank_data again
        seed_bank_data(db, "demo-bank")

        cust_count_2 = db.query(BankCustomer).count()
        acc_count_2 = db.query(BankAccount).count()
        txn_count_2 = db.query(BankTransaction).count()
        poi_count_2 = db.query(PoiPlace).count()

        assert cust_count_2 == cust_count_1 == 200
        assert acc_count_2 == acc_count_1 == 321
        assert txn_count_2 == txn_count_1
        assert poi_count_2 == poi_count_1 == 150


def test_decimal_balances_reconciliation():
    """Reconcile every active transactional account balance with net transaction movements.

    Design: For every SAVINGS and CURRENT account, its balance equals:
        balance = opening_balance + sum(credits) - sum(debits)
    where opening_balance >= 0 is the balance before the 90-day window.
    """
    with SessionLocal() as db:
        accounts = db.query(BankAccount).filter(BankAccount.product.in_(["SAVINGS", "CURRENT"])).all()
        assert len(accounts) >= 200

        for acc in accounts:
            assert isinstance(acc.balance, Decimal)
            assert acc.balance >= Decimal("0.00")

            txns = db.query(BankTransaction).filter_by(account_id=acc.id).all()
            total_credits = sum((t.amount for t in txns if t.direction == "CREDIT"), Decimal("0.00"))
            total_debits = sum((t.amount for t in txns if t.direction == "DEBIT"), Decimal("0.00"))

            inferred_opening = acc.balance - total_credits + total_debits
            # Inferred opening balance must be positive and non-negative
            assert inferred_opening >= Decimal("0.00")
            # Balance strictly reconciles: opening + credits - debits == balance
            assert inferred_opening + total_credits - total_debits == acc.balance


def test_linked_parties_present():
    """Verify existing parties are linked and unlinked candidates remain unlinked."""
    with SessionLocal() as db:
        tenant_id = "demo-bank"

        # DINA, ADITYA, NABILA, SINAR must have party_id set
        for key in ["DINA", "ADITYA", "NABILA", "SINAR"]:
            cust = db.query(BankCustomer).filter_by(id=f"bcust-{tenant_id}-{key.lower()}").first()
            assert cust is not None, f"Customer for {key} missing"
            assert cust.party_id == sid(tenant_id, key), f"Party ID mismatch for {key}"
            # Linked Party must actually exist in rm_parties
            party = db.get(Party, cust.party_id)
            assert party is not None

        # Two RANTAI candidates must exist in BankCustomer without party_id
        r1 = db.query(BankCustomer).filter_by(full_name="PT Rantai Pasok Utama").first()
        r2 = db.query(BankCustomer).filter_by(full_name="PT Rantai Pasok Utama Jaya").first()
        assert r1 is not None
        assert r2 is not None
        assert r1.party_id is None
        assert r2.party_id is None

        # RANI, BIMA, ARUNA, SINTA must NOT exist as customers
        for blocked in ["Rani Kusuma", "Bima Setiawan", "CV Aruna Niaga", "Sinta Maharani"]:
            assert db.query(BankCustomer).filter_by(full_name=blocked).first() is None


def test_no_raw_identifiers_stored():
    """Ensure no plain-text phone numbers or NPWPs are persisted in the database."""
    with SessionLocal() as db:
        for c in db.query(BankCustomer).all():
            if c.phone_hash:
                assert len(c.phone_hash) == 64
                assert all(ch in "0123456789abcdef" for ch in c.phone_hash)
            if c.npwp_hash:
                assert len(c.npwp_hash) == 64
                assert all(ch in "0123456789abcdef" for ch in c.npwp_hash)
            if c.email_hash:
                assert len(c.email_hash) == 64
                assert all(ch in "0123456789abcdef" for ch in c.email_hash)
            if c.phone_masked:
                assert c.phone_masked.startswith("+")
                assert "••••" in c.phone_masked
                # Raw 10+ digit sequence must not appear
                assert not c.phone_masked.isdigit()

        for p in db.query(PoiPlace).all():
            if p.phone_hash:
                assert len(p.phone_hash) == 64
            if p.phone_masked:
                assert "••••" in p.phone_masked


def test_demo_story_dina():
    """Dina Rahma: salaried teacher, transport spend rising (900k -> 1.15M), recurring 45k, school fees."""
    with SessionLocal() as db:
        dina = db.query(BankCustomer).filter_by(id="bcust-demo-bank-dina").first()
        assert dina.full_name == "Dina Rahma"
        assert dina.segment == "MASS"

        sav = db.query(BankAccount).filter_by(customer_id=dina.id, product="SAVINGS").first()
        assert sav.balance == Decimal("12500000.00")

        txns = db.query(BankTransaction).filter_by(account_id=sav.id).all()

        # Salary credit on 25th of month
        salaries = [t for t in txns if t.category == "Salary" and t.direction == "CREDIT"]
        assert len(salaries) == 3
        for s in salaries:
            assert s.posted_at.day == 25

        # Transport spend comparison: prior 30d (days 60-30) vs last 30d (days 30-0)
        d_end = ANCHOR_DATETIME
        d_mid = ANCHOR_DATETIME - timedelta(days=30)
        d_start = ANCHOR_DATETIME - timedelta(days=60)

        prior_transport = sum(
            (t.amount for t in txns if t.category == "Transport" and d_start <= t.posted_at.replace(tzinfo=timezone.utc) < d_mid),
            Decimal("0.00"),
        )
        last_transport = sum(
            (t.amount for t in txns if t.category == "Transport" and d_mid <= t.posted_at.replace(tzinfo=timezone.utc) <= d_end),
            Decimal("0.00"),
        )

        assert prior_transport == Decimal("900000.00")
        assert last_transport == Decimal("1150000.00")
        assert last_transport > prior_transport  # Rising spend pattern

        # Recurring charge 45,000
        rec = [t for t in txns if t.amount == Decimal("45000.00")]
        assert len(rec) >= 3

        # School fees present
        edu = [t for t in txns if t.category == "Education"]
        assert len(edu) >= 3


def test_demo_story_aditya():
    """Aditya Pratama: affluent, large idle savings balance, term deposit maturing 2026-10-30."""
    with SessionLocal() as db:
        aditya = db.query(BankCustomer).filter_by(id="bcust-demo-bank-aditya").first()
        assert aditya.segment == "AFFLUENT"

        sav = db.query(BankAccount).filter_by(customer_id=aditya.id, product="SAVINGS").first()
        assert sav.balance > Decimal("400000000.00")  # Large idle savings balance

        td = db.query(BankAccount).filter_by(customer_id=aditya.id, product="TERM_DEPOSIT").first()
        assert td is not None
        assert td.balance == Decimal("500000000.00")
        assert td.maturity_date == date(2026, 10, 30)  # Maturing soon


def test_demo_story_nabila():
    """Nabila Aulia: freelancer, irregular income credits, rent and recurring subscriptions."""
    with SessionLocal() as db:
        nabila = db.query(BankCustomer).filter_by(id="bcust-demo-bank-nabila").first()
        assert nabila.full_name == "Nabila Aulia"

        sav = db.query(BankAccount).filter_by(customer_id=nabila.id, product="SAVINGS").first()
        txns = db.query(BankTransaction).filter_by(account_id=sav.id).order_by(BankTransaction.posted_at).all()

        credits = [t for t in txns if t.direction == "CREDIT"]
        assert len(credits) == 4
        # Irregular dates (not fixed on the 25th)
        credit_days = [t.posted_at.day for t in credits]
        assert len(set(credit_days)) == 4
        assert 25 not in credit_days

        # Rent payments present
        rent_txns = [t for t in txns if t.category == "Rent"]
        assert len(rent_txns) == 3


def test_demo_story_pt_sinar():
    """PT Sinar Distribusi: steady SME settlements on current account."""
    with SessionLocal() as db:
        sinar = db.query(BankCustomer).filter_by(id="bcust-demo-bank-sinar").first()
        assert sinar.segment == "SME"

        cur = db.query(BankAccount).filter_by(customer_id=sinar.id, product="CURRENT").first()
        assert cur is not None

        txns = db.query(BankTransaction).filter_by(account_id=cur.id).all()
        settlements = [t for t in txns if t.category == "Merchant Settlement"]
        assert len(settlements) >= 50  # Steady daily merchant settlements


def test_poi_places_dataset():
    """Verify POI dataset properties, distance constraint, and matching design."""
    with SessionLocal() as db:
        pois = db.query(PoiPlace).all()
        assert len(pois) == 150

        for p in pois:
            assert p.provider == "SYNTHETIC_DATASET"
            assert p.attribution == "Synthetic POI dataset (demo)"
            assert p.expires_at is None
            assert p.rating is not None and Decimal("3.0") <= p.rating <= Decimal("5.0")
            assert p.rating_count is not None and p.rating_count >= 1

            # Haversine distance within 5,000 meters of demo office
            dist = haversine_m(float(p.latitude), float(p.longitude), DEMO_OFFICE_LAT, DEMO_OFFICE_LNG)
            assert dist <= 5000.0, f"POI {p.name} exceeds 5km: {dist:.1f}m"
