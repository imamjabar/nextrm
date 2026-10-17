"""Tests for core-banking insights pipeline, scoring, copy phrasing and validators."""
from datetime import datetime, date, timedelta
from decimal import Decimal
import os
import pytest

from app.core.database import SessionLocal
from app.models.entities import utc_now
from app.models.banking import BankCustomer, BankAccount, BankTransaction
from app.models.relationships import Party, Source
from app.services.insights_pipeline import (
    customer_for_party,
    features_for,
    insight_cards,
    score_candidate,
    refresh_bank_data_source,
    METHOD,
)
from app.services.assistant.nudge_copy import (
    phrase_nudge,
    validate_numbers_match_values,
    validate_no_promises_or_urls,
    deterministic_nudge_copy,
)
from app.services.assistant.engine import ProviderFailure


def create_test_customer_and_accounts(db, tenant_id="demo-bank", party_id=None):
    """Helper to create a BankCustomer with active savings and term deposit accounts."""
    cid = f"bc-test-{datetime.now().timestamp()}"
    cust = BankCustomer(
        id=cid,
        tenant_id=tenant_id,
        cif="CIF-TEST-001",
        kind="PERSON",
        full_name="Budi Santoso",
        normalized_name="BUDI SANTOSO",
        address="Jl. Sudirman No. 1",
        city="Bekasi",
        segment="MASS",
        opened_at=date(2025, 1, 1),
        party_id=party_id,
        mode="SYNTHETIC",
    )
    db.add(cust)
    db.flush()

    acc_sav = BankAccount(
        id=f"acc-sav-{cid}",
        tenant_id=tenant_id,
        customer_id=cid,
        account_masked="•••• 1234",
        product="SAVINGS",
        currency="IDR",
        balance=Decimal("10000000.00"),
        status="ACTIVE",
        opened_at=date(2025, 1, 1),
    )
    db.add(acc_sav)
    db.flush()
    return cust, acc_sav


def test_features_salary_detection():
    with SessionLocal() as db:
        cust, acc = create_test_customer_and_accounts(db)
        as_of = datetime(2026, 10, 26, 10, 0, 0)
        # 3 salary credits on day 25 of Aug, Sep, Oct
        for month in (8, 9, 10):
            tx = BankTransaction(
                id=f"tx-sal-{month}",
                tenant_id=cust.tenant_id,
                account_id=acc.id,
                customer_id=cust.id,
                posted_at=datetime(2026, month, 25, 9, 0, 0),
                amount=Decimal("15000000.00"),
                direction="CREDIT",
                category="Salary",
                merchant="PT Tech Indonesia",
                description="Payroll Salary Transfer",
                channel="TRANSFER",
            )
            db.add(tx)
        db.commit()

        feat = features_for(db, cust, as_of)
        assert feat["salary_detected"] is True
        assert feat["is_regular_salary"] is True
        assert feat["salary_amount"] == Decimal("15000000.00")
        assert feat["salary_day"] == 25


def test_features_category_delta():
    with SessionLocal() as db:
        cust, acc = create_test_customer_and_accounts(db)
        as_of = datetime(2026, 10, 26, 10, 0, 0)

        # Previous 30 days: Transport spend = 800,000.00
        tx_prev = BankTransaction(
            id="tx-trans-prev",
            tenant_id=cust.tenant_id,
            account_id=acc.id,
            customer_id=cust.id,
            posted_at=as_of - timedelta(days=40),
            amount=Decimal("800000.00"),
            direction="DEBIT",
            category="Transport",
            merchant="KAI Commuter",
            description="Train pass",
            channel="POS",
        )
        db.add(tx_prev)

        # Current 30 days: Transport spend = 1,200,000.00
        tx_curr = BankTransaction(
            id="tx-trans-curr",
            tenant_id=cust.tenant_id,
            account_id=acc.id,
            customer_id=cust.id,
            posted_at=as_of - timedelta(days=10),
            amount=Decimal("1200000.00"),
            direction="DEBIT",
            category="Transport",
            merchant="Grab Transport",
            description="Ride hailing",
            channel="MOBILE",
        )
        db.add(tx_curr)
        db.commit()

        feat = features_for(db, cust, as_of)
        assert feat["focus_category"] == "Transport"
        assert feat["focus_spend"]["current"] == Decimal("1200000.00")
        assert feat["focus_spend"]["previous"] == Decimal("800000.00")
        assert feat["focus_spend"]["delta"] == Decimal("400000.00")
        assert feat["focus_spend"]["change_percent"] == Decimal("50.00")


def test_features_recurring_bill():
    with SessionLocal() as db:
        cust, acc = create_test_customer_and_accounts(db)
        as_of = datetime(2026, 10, 26, 10, 0, 0)

        # 3 recurring monthly PLN bills
        for month, day in [(8, 5), (9, 5), (10, 5)]:
            tx = BankTransaction(
                id=f"tx-pln-{month}",
                tenant_id=cust.tenant_id,
                account_id=acc.id,
                customer_id=cust.id,
                posted_at=datetime(2026, month, day, 8, 30, 0),
                amount=Decimal("750000.00"),
                direction="DEBIT",
                category="Utilities",
                merchant="PLN Electricity",
                description="Listrik Pascabayar",
                channel="MOBILE",
            )
            db.add(tx)
        db.commit()

        feat = features_for(db, cust, as_of)
        rec = next((b for b in feat["recurring_bills"] if "PLN" in b["merchant"]), None)
        assert rec is not None
        assert rec["cadence"] == "MONTHLY"
        assert rec["amount"] == Decimal("750000.00")
        assert feat["total_recurring_monthly"] >= Decimal("750000.00")


def test_features_idle_cash():
    with SessionLocal() as db:
        cust, acc = create_test_customer_and_accounts(db)
        acc.balance = Decimal("80000000.00")  # 80M savings
        as_of = datetime(2026, 10, 26, 10, 0, 0)

        # Outflow over 90 days = 30M (avg 10M/month -> 3x is 30M)
        tx = BankTransaction(
            id="tx-outflow",
            tenant_id=cust.tenant_id,
            account_id=acc.id,
            customer_id=cust.id,
            posted_at=as_of - timedelta(days=20),
            amount=Decimal("30000000.00"),
            direction="DEBIT",
            category="General",
            merchant="Various",
            description="Expenses",
            channel="POS",
        )
        db.add(tx)
        db.commit()

        feat = features_for(db, cust, as_of)
        # monthly outflow = 30M / 3 = 10M. 3x outflow = 30M. Idle cash = 80M - 30M = 50M.
        assert feat["has_idle_cash"] is True
        assert feat["monthly_outflow"] == Decimal("10000000.00")
        assert feat["idle_cash"] == Decimal("50000000.00")


def test_features_low_balance_gap():
    with SessionLocal() as db:
        pid = f"party-{datetime.now().timestamp()}"
        party = Party(
            id=pid,
            tenant_id="demo-bank",
            kind="PERSON",
            name="Test Low Balance",
            segment="MASS",
            owner_id="usr-maya",
            relationship="EXISTING_CUSTOMER",
            identity="CONFIRMED",
            contact="ALLOWED",
            locality="Bekasi",
            context_json="{}",
        )
        db.add(party)
        db.flush()

        cust, acc = create_test_customer_and_accounts(db, party_id=pid)
        acc.balance = Decimal("2000000.00")  # Low balance 2M
        as_of = datetime(2026, 10, 10, 10, 0, 0)

        # Recurring bill with next expected date in 5 days (Oct 15) for 3.5M
        tx = BankTransaction(
            id="tx-bill-gap",
            tenant_id=cust.tenant_id,
            account_id=acc.id,
            customer_id=cust.id,
            posted_at=datetime(2026, 9, 15, 10, 0, 0),
            amount=Decimal("3500000.00"),
            direction="DEBIT",
            category="Utilities",
            merchant="School Tuition",
            description="SPP Bulanan",
            channel="TRANSFER",
        )
        db.add(tx)
        db.commit()

        feat = features_for(db, cust, as_of)
        assert feat["commitments_14d"] == Decimal("3500000.00")
        assert feat["cash_flow_diff"] == Decimal("-1500000.00")
        assert feat["has_cash_gap"] is True

        cards = insight_cards(db, party, as_of)
        cash_card = cards[0]
        assert cash_card["key"] == "cash_flow"
        assert cash_card["status"] == "GAP"
        assert cash_card["values"]["difference"] == "-1500000.00"


def test_features_term_deposit_maturity():
    with SessionLocal() as db:
        cust, acc = create_test_customer_and_accounts(db)
        as_of = datetime(2026, 10, 15, 10, 0, 0)

        acc_td = BankAccount(
            id=f"acc-td-{cust.id}",
            tenant_id=cust.tenant_id,
            customer_id=cust.id,
            account_masked="•••• 9876",
            product="TERM_DEPOSIT",
            currency="IDR",
            balance=Decimal("50000000.00"),
            status="ACTIVE",
            opened_at=date(2025, 10, 30),
            maturity_date=date(2026, 10, 30),  # Matures in 15 days
        )
        db.add(acc_td)
        db.commit()

        feat = features_for(db, cust, as_of)
        assert feat["has_maturing_td"] is True
        assert feat["maturing_td"]["days_to_maturity"] == 15
        assert feat["maturing_td"]["balance"] == Decimal("50000000.00")


def test_ranking_order_care_first():
    # Care first: CARE with a gap strictly dominates GUIDANCE and COMMERCIAL
    score_care_gap = score_candidate("CARE", magnitude_val=Decimal("0.80"), recency_days=0, is_urgent_care=True)
    score_care_routine = score_candidate("CARE", magnitude_val=Decimal("0.40"), recency_days=0, is_urgent_care=False)
    score_guidance = score_candidate("GUIDANCE", magnitude_val=Decimal("1.00"), recency_days=0)
    score_commercial_large = score_candidate("COMMERCIAL", magnitude_val=Decimal("1.00"), recency_days=0)

    assert score_care_gap > score_care_routine
    assert score_care_routine > score_guidance
    assert score_guidance > score_commercial_large
    assert score_commercial_large == Decimal("1.0000")
    assert score_care_gap == Decimal("80.0000")


def test_deterministic_copy_numbers_equal_values():
    card = {
        "key": "spending",
        "title": "Transport spending",
        "status": "AVAILABLE",
        "values": {
            "previous_spend": "900000.00",
            "current_spend": "1150000.00",
            "change": "250000.00",
            "change_percent": "27.78",
        },
        "explanation": "Comparable periods test.",
    }
    result = phrase_nudge(card)
    assert result["mode"] == "SIMULATED"
    full_text = f"{result['title']} {result['body']} {result['prompt']}"
    # Validates without raising ValueError
    validate_numbers_match_values(full_text, card["values"])


def test_validator_rejects_invented_numbers():
    card_values = {"available": "12500000.00", "commitments": "4700000.00", "difference": "7800000.00"}

    # Legitimate numbers from card pass
    validate_numbers_match_values("Your available funds are 12,500,000.00 IDR.", card_values)

    # Invented number raises ValueError
    with pytest.raises(ValueError, match="Invented number '500000'"):
        validate_numbers_match_values("You can save 500000 IDR every month.", card_values)


def test_validator_rejects_product_promises_and_urls():
    with pytest.raises(ValueError, match="URLs are strictly forbidden"):
        validate_no_promises_or_urls("Visit https://bank.example.com to learn more.")

    with pytest.raises(ValueError, match="Product promises/guarantees are strictly forbidden"):
        validate_no_promises_or_urls("This product offers a guaranteed return on investment.")


def test_phrase_nudge_fallback_on_provider_failure(monkeypatch):
    monkeypatch.setenv("NEXTRM_AI_PROVIDER", "gemini")

    def mock_structured_generate(*args, **kwargs):
        raise ProviderFailure("Upstream Gemini service timeout.")

    import app.services.assistant.nudge_copy as nc
    monkeypatch.setattr(nc, "structured_generate", mock_structured_generate)

    card = {
        "key": "cash_flow",
        "title": "Upcoming commitments",
        "status": "GAP",
        "values": {"available": "1000000.00", "commitments": "2500000.00", "difference": "-1500000.00"},
        "explanation": "Gap detected.",
    }
    res = nc.phrase_nudge(card)
    assert res["mode"] == "DETERMINISTIC"
    assert res["model"] == "fallback-rejected"
    assert "rejected" in res["rejection_reason"].lower() or "upstream" in res["rejection_reason"].lower()
    assert "-1,500,000" in res["body"]


def test_customer_without_bank_data_keeps_unavailable():
    with SessionLocal() as db:
        p = Party(
            id="party-no-bank",
            tenant_id="demo-bank",
            kind="PERSON",
            name="No Bank Customer",
            segment="MASS",
            owner_id="usr-maya",
            relationship="EXISTING_CUSTOMER",
            identity="CONFIRMED",
            contact="ALLOWED",
            locality="Jakarta",
            context_json="{}",
        )
        db.add(p)
        db.commit()

        cards = insight_cards(db, p)
        assert len(cards) >= 3
        for card in cards:
            assert card["status"] == "UNAVAILABLE"
            assert card["values"] == {}


def test_seeded_customer_stories():
    with SessionLocal() as db:
        dina = db.query(Party).filter_by(name="Dina Rahma").first()
        aditya = db.query(Party).filter_by(name="Aditya Pratama").first()
        nabila = db.query(Party).filter_by(name="Nabila Aulia").first()

        if not dina or not customer_for_party(db, dina):
            pytest.skip("Bank seed not present yet in database")

        # 1. Dina: salaried teacher, transport spend rising, school commitments
        dina_cards = insight_cards(db, dina)
        dina_spend = next(c for c in dina_cards if c["key"] == "spending")
        assert dina_spend["status"] == "AVAILABLE"
        dina_sal = next(c for c in dina_cards if c["key"] == "salary")
        assert dina_sal["status"] == "AVAILABLE"

        # 2. Aditya: affluent, idle cash, term deposit maturing
        aditya_cust = customer_for_party(db, aditya)
        if aditya_cust:
            aditya_cards = insight_cards(db, aditya)
            aditya_idle = next((c for c in aditya_cards if c["key"] == "idle_cash"), None)
            aditya_td = next((c for c in aditya_cards if c["key"] == "term_deposit"), None)
            assert aditya_idle is not None
            assert aditya_td is not None

        # 3. Nabila: designer, freelancer, irregular income
        nabila_cust = customer_for_party(db, nabila)
        if nabila_cust:
            nabila_cards = insight_cards(db, nabila)
            assert any(c["key"] == "salary" for c in nabila_cards)
