"""Repeat-safe, deterministic core-banking fixtures and POI seeding for NextRM demo.

Balance Reconciliation Design:
For every active BankAccount (SAVINGS and CURRENT), its balance is explicitly defined as:
    account.balance = opening_balance + total_credits - total_debits
where:
    total_credits = sum(tx.amount for tx in transactions if tx.direction == 'CREDIT')
    total_debits = sum(tx.amount for tx in transactions if tx.direction == 'DEBIT')
    opening_balance is the deterministic account balance at day -90 before the transaction history window.
All amounts are Decimal IDR with 2 decimal places.
TERM_DEPOSIT and CREDIT_CARD accounts carry fixed contractual balances.
"""
import hashlib
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.orm import Session

from ..models.banking import BankAccount, BankCustomer, BankGoal, BankHolding, BankTransaction, PoiPlace
from ..models.relationships import Party
from .identity_keys import (
    email_hash,
    mask_phone,
    normalize_name,
    npwp_hash,
    phone_hash,
)

ROOT = Path(__file__).resolve().parents[4]
CUSTOMERS_JSON = ROOT / "data/synthetic/bank/customers.json"
PLACES_JSON = ROOT / "data/synthetic/poi/places.json"
PLANNING_JSON = ROOT / "data/synthetic/bank/planning.json"

ANCHOR_DATE = date(2026, 10, 17)
ANCHOR_DATETIME = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
WINDOW_DAYS = 90


def sid(tenant: str, suffix: str) -> str:
    return hashlib.sha256(tenant.encode()).hexdigest()[:8] + "-" + suffix


def _dec(val: str | int | float) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def seed_bank_data(db: Session, tenant_id: str = "demo-bank") -> None:
    """Seed synthetic core-banking customers, accounts, 90-day transactions, and POIs.

    Deterministic and repeat-safe: checks for existence before adding rows.
    Uses fixed anchor date 2026-10-17 and fixed random seed so numbers remain stable.
    """
    if not CUSTOMERS_JSON.exists() or not PLACES_JSON.exists():
        return

    customers_data = json.loads(CUSTOMERS_JSON.read_text())
    places_data = json.loads(PLACES_JSON.read_text())
    planning = json.loads(PLANNING_JSON.read_text()) if PLANNING_JSON.exists() else {}

    # 1. Seed Bank Customers
    cust_map = {}  # key -> BankCustomer
    for item in customers_data:
        cid = f"bcust-{tenant_id}-{item['key'].lower()}"
        existing = db.get(BankCustomer, cid)
        if not existing:
            # Check by CIF as well
            existing = db.query(BankCustomer).filter_by(tenant_id=tenant_id, cif=item["cif"]).first()

        if existing:
            cust_map[item["key"]] = existing
            continue

        party_id = None
        if item.get("party_key"):
            target_pid = sid(tenant_id, item["party_key"])
            if db.get(Party, target_pid):
                party_id = target_pid

        row = BankCustomer(
            id=cid,
            tenant_id=tenant_id,
            cif=item["cif"],
            kind=item["kind"],
            full_name=item["full_name"],
            normalized_name=normalize_name(item["full_name"]),
            nik_hash=None,
            npwp_hash=npwp_hash(tenant_id, item["npwp"]) if item.get("npwp") else None,
            phone_hash=phone_hash(tenant_id, item["phone"]) if item.get("phone") else None,
            email_hash=email_hash(tenant_id, item["email"]) if item.get("email") else None,
            phone_masked=mask_phone(item["phone"]) if item.get("phone") else None,
            address=item["address"],
            city=item["city"],
            latitude=Decimal(str(item["latitude"])) if item.get("latitude") is not None else None,
            longitude=Decimal(str(item["longitude"])) if item.get("longitude") is not None else None,
            segment=item["segment"],
            opened_at=date.fromisoformat(item["opened_at"]),
            party_id=party_id,
            mode="SYNTHETIC",
        )
        db.add(row)
        cust_map[item["key"]] = row

    db.flush()

    # 2. Seed Accounts and Transactions per customer
    for idx, item in enumerate(customers_data, start=1):
        cust_key = item["key"]
        customer = cust_map[cust_key]
        cust_id = customer.id
        persona = item.get("persona", "salaried")
        segment = item.get("segment", "MASS")
        kind = item.get("kind", "PERSON")

        # 2.1 Savings Account (all customers)
        sav_id = f"bacc-{cust_id}-sav"
        sav_acc = db.get(BankAccount, sav_id)
        if not sav_acc:
            # Generate transactions for savings account
            txns_spec, opening_balance = _generate_savings_txns(cust_key, persona, segment, idx)
            net_change = sum((t["amount"] if t["direction"] == "CREDIT" else -t["amount"]) for t in txns_spec)
            final_balance = opening_balance + net_change

            sav_acc = BankAccount(
                id=sav_id,
                tenant_id=tenant_id,
                customer_id=cust_id,
                account_masked=f"••••{1000 + idx:04d}",
                product="SAVINGS",
                currency="IDR",
                balance=final_balance,
                status="ACTIVE",
                opened_at=customer.opened_at,
                maturity_date=None,
            )
            db.add(sav_acc)
            db.flush()

            for s_idx, t in enumerate(txns_spec, start=1):
                txn_id = f"btxn-{sav_id}-{s_idx:04d}"
                db.add(
                    BankTransaction(
                        id=txn_id,
                        tenant_id=tenant_id,
                        account_id=sav_id,
                        customer_id=cust_id,
                        posted_at=t["posted_at"],
                        amount=t["amount"],
                        direction=t["direction"],
                        category=t["category"],
                        merchant=t["merchant"],
                        description=t["description"],
                        channel=t["channel"],
                    )
                )

        # 2.2 Current Account (SME and CORPORATE)
        if kind == "ORGANIZATION" or segment in {"SME", "CORPORATE"}:
            cur_id = f"bacc-{cust_id}-cur"
            cur_acc = db.get(BankAccount, cur_id)
            if not cur_acc:
                cur_txns, cur_opening = _generate_current_txns(cust_key, persona, segment, idx)
                cur_net = sum((t["amount"] if t["direction"] == "CREDIT" else -t["amount"]) for t in cur_txns)
                cur_final = cur_opening + cur_net

                cur_acc = BankAccount(
                    id=cur_id,
                    tenant_id=tenant_id,
                    customer_id=cust_id,
                    account_masked=f"••••{5000 + idx:04d}",
                    product="CURRENT",
                    currency="IDR",
                    balance=cur_final,
                    status="ACTIVE",
                    opened_at=customer.opened_at,
                    maturity_date=None,
                )
                db.add(cur_acc)
                db.flush()

                for c_idx, t in enumerate(cur_txns, start=1):
                    txn_id = f"btxn-{cur_id}-{c_idx:04d}"
                    db.add(
                        BankTransaction(
                            id=txn_id,
                            tenant_id=tenant_id,
                            account_id=cur_id,
                            customer_id=cust_id,
                            posted_at=t["posted_at"],
                            amount=t["amount"],
                            direction=t["direction"],
                            category=t["category"],
                            merchant=t["merchant"],
                            description=t["description"],
                            channel=t["channel"],
                        )
                    )

        # 2.3 Term Deposit (AFFLUENT customers incl. Aditya)
        if segment == "AFFLUENT":
            td_id = f"bacc-{cust_id}-td"
            if not db.get(BankAccount, td_id):
                if cust_key == "ADITYA":
                    td_maturity = date(2026, 10, 30)
                    td_bal = _dec(500000000)
                else:
                    td_maturity = ANCHOR_DATE + timedelta(days=14 + (idx * 13) % 180)
                    td_bal = _dec(100000000 + ((idx * 25000000) % 500000000))

                db.add(
                    BankAccount(
                        id=td_id,
                        tenant_id=tenant_id,
                        customer_id=cust_id,
                        account_masked=f"••••{8000 + idx:04d}",
                        product="TERM_DEPOSIT",
                        currency="IDR",
                        balance=td_bal,
                        status="ACTIVE",
                        opened_at=date(2026, 4, 30) if cust_key == "ADITYA" else customer.opened_at,
                        maturity_date=td_maturity,
                    )
                )

        # 2.4 Credit Card (AFFLUENT + some salaried mass)
        card_override = (planning.get("credit_cards") or {}).get(cust_key)
        if segment == "AFFLUENT" or (persona == "salaried" and idx % 3 == 0) or card_override:
            cc_id = f"bacc-{cust_id}-cc"
            if not db.get(BankAccount, cc_id):
                if card_override:
                    cc_bal = _dec(card_override["balance"])
                else:
                    cc_bal = _dec(0) if segment != "AFFLUENT" else _dec(15450000)
                db.add(
                    BankAccount(
                        id=cc_id,
                        tenant_id=tenant_id,
                        customer_id=cust_id,
                        account_masked=f"••••{4000 + idx:04d}",
                        product="CREDIT_CARD",
                        currency="IDR",
                        balance=cc_bal,
                        status="ACTIVE",
                        opened_at=customer.opened_at,
                        maturity_date=None,
                        payment_due_day=card_override["due_day"] if card_override else None,
                    )
                )

    db.flush()
    _seed_planning(db, tenant_id, planning, cust_map)

    # 3. Seed POI Places
    for p in places_data:
        provider_place_id = p["provider_place_id"]
        pid = f"poi-{tenant_id}-{provider_place_id.replace(':', '-')}"
        existing = db.get(PoiPlace, pid)
        if not existing:
            existing = db.query(PoiPlace).filter_by(
                tenant_id=tenant_id,
                provider="SYNTHETIC_DATASET",
                provider_place_id=provider_place_id
            ).first()

        if existing:
            continue

        raw_phone = p.get("phone")
        p_row = PoiPlace(
            id=pid,
            tenant_id=tenant_id,
            provider="SYNTHETIC_DATASET",
            provider_place_id=provider_place_id,
            name=p["name"],
            primary_type=p["primary_type"],
            address=p["address"],
            latitude=Decimal(str(p["latitude"])),
            longitude=Decimal(str(p["longitude"])),
            phone_hash=phone_hash(tenant_id, raw_phone) if raw_phone else None,
            phone_masked=mask_phone(raw_phone) if raw_phone else None,
            website=p.get("website"),
            rating=Decimal(str(p["rating"])) if p.get("rating") is not None else None,
            rating_count=p.get("rating_count"),
            attribution="Synthetic POI dataset (demo)",
            fetched_at=ANCHOR_DATETIME,
            expires_at=None,
            match_status="UNREVIEWED",
            matched_customer_id=None,
            match_score=None,
            match_reasons_json="[]",
            matched_at=None,
            prospect_id=None,
        )
        db.add(p_row)

    db.commit()

    # 4. Optional call to customer_match if module exists
    try:
        from app.services.customer_match import match_all_pois
        match_all_pois(db, tenant_id)
        db.commit()
    except ImportError:
        pass



def _seed_planning(db: Session, tenant_id: str, planning: dict, cust_map: dict) -> None:
    """Account terms, savings goals and investment holdings. Repeat-safe: existing rows are never overwritten."""
    terms = planning.get("account_terms", {})
    for account in db.query(BankAccount).filter_by(tenant_id=tenant_id).all():
        spec = terms.get(account.product)
        if not spec:
            continue
        if account.interest_rate_percent is None:
            account.interest_rate_percent = _dec(spec["interest_rate_percent"])
        if account.product == "CREDIT_CARD":
            balance = Decimal(str(account.balance))
            if account.minimum_payment is None:
                floor = _dec(spec["minimum_floor"])
                account.minimum_payment = max(_dec(balance * _dec(spec["minimum_percent"]) / Decimal(100)), floor) if balance > 0 else _dec(0)
            if account.payment_due_day is None:
                account.payment_due_day = 5 + int(hashlib.sha256(account.id.encode()).hexdigest(), 16) % 20
    as_of = ANCHOR_DATETIME.replace(tzinfo=None)
    for key, rows in (planning.get("goals") or {}).items():
        customer = cust_map.get(key)
        for number, row in enumerate(rows if customer else [], start=1):
            goal_id = f"bgoal-{customer.id}-{number}"
            if not db.get(BankGoal, goal_id):
                db.add(BankGoal(
                    id=goal_id, tenant_id=tenant_id, customer_id=customer.id, name=row["name"],
                    target_amount=_dec(row["target_amount"]), saved_amount=_dec(row["saved_amount"]),
                    monthly_plan=_dec(row["monthly_plan"]), target_date=date.fromisoformat(row["target_date"]),
                    status="ACTIVE", mode="SYNTHETIC",
                ))
    for key, rows in (planning.get("holdings") or {}).items():
        customer = cust_map.get(key)
        for number, row in enumerate(rows if customer else [], start=1):
            holding_id = f"bhold-{customer.id}-{number}"
            if not db.get(BankHolding, holding_id):
                db.add(BankHolding(
                    id=holding_id, tenant_id=tenant_id, customer_id=customer.id, instrument=row["instrument"],
                    asset_class=row["asset_class"], cost_basis=_dec(row["cost_basis"]), market_value=_dec(row["market_value"]),
                    value_30d_ago=_dec(row["value_30d_ago"]) if row.get("value_30d_ago") else None,
                    as_of=as_of, mode="SYNTHETIC",
                ))
    db.flush()

def _dt(d: date, hour: int = 10, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour, minute, 0), tzinfo=timezone.utc)


def _generate_savings_txns(cust_key: str, persona: str, segment: str, idx: int) -> tuple[list[dict], Decimal]:
    """Generate 90-day transactions and opening balance for a savings account."""
    txns = []

    # ---------------------------------------------------------
    # Demo Story 1: Dina Rahma (teacher, salaried)
    # ---------------------------------------------------------
    if cust_key == "DINA":
        target_final_balance = _dec(12500000)
        # Salary on 25th of July, August, September
        for s_date in [date(2026, 7, 25), date(2026, 8, 25), date(2026, 9, 25)]:
            txns.append({
                "posted_at": _dt(s_date, 9, 30),
                "amount": _dec(8500000),
                "direction": "CREDIT",
                "category": "Salary",
                "merchant": "Yayasan Pendidikan Kartika",
                "description": "Gaji Bulanan Guru",
                "channel": "TRANSFER"
            })

        # Transport spend prior 30d (2026-08-18 to 2026-09-17): Exactly 900,000.00
        prior_transport = [
            (date(2026, 8, 20), 150000, "Gojek Indonesia", "GoRide Transportasi Harian", "QRIS"),
            (date(2026, 8, 27), 250000, "Grab Indonesia", "GrabCar Perjalanan Dinas", "QRIS"),
            (date(2026, 9, 3), 200000, "Gojek Indonesia", "GoRide Transportasi", "QRIS"),
            (date(2026, 9, 12), 300000, "KAI Commuter", "Top Up Kartu Multi Trip KRL", "EDC"),
        ]
        for d, amt, m, desc, ch in prior_transport:
            txns.append({
                "posted_at": _dt(d, 8, 15),
                "amount": _dec(amt),
                "direction": "DEBIT",
                "category": "Transport",
                "merchant": m,
                "description": desc,
                "channel": ch
            })

        # Transport spend last 30d (2026-09-18 to 2026-10-17): Exactly 1,150,000.00 (rising!)
        last_transport = [
            (date(2026, 9, 20), 250000, "Grab Indonesia", "GrabCar Dinas Luar Kota", "QRIS"),
            (date(2026, 9, 28), 300000, "Gojek Indonesia", "GoCar Transportasi", "QRIS"),
            (date(2026, 10, 6), 350000, "Grab Indonesia", "GrabCar Transportasi Harian", "QRIS"),
            (date(2026, 10, 14), 250000, "KAI Commuter", "Top Up Kartu Multi Trip KRL", "EDC"),
        ]
        for d, amt, m, desc, ch in last_transport:
            txns.append({
                "posted_at": _dt(d, 8, 30),
                "amount": _dec(amt),
                "direction": "DEBIT",
                "category": "Transport",
                "merchant": m,
                "description": desc,
                "channel": ch
            })

        # Recurring charge: 45,000.00
        for r_date in [date(2026, 7, 28), date(2026, 8, 28), date(2026, 9, 28)]:
            txns.append({
                "posted_at": _dt(r_date, 10, 0),
                "amount": _dec(45000),
                "direction": "DEBIT",
                "category": "Entertainment",
                "merchant": "Spotify AB",
                "description": "Langganan Spotify Premium",
                "channel": "AUTO_DEBIT"
            })

        # School fees & education expenses
        for ed_date in [date(2026, 8, 5), date(2026, 9, 5), date(2026, 10, 5)]:
            txns.append({
                "posted_at": _dt(ed_date, 10, 30),
                "amount": _dec(1500000),
                "direction": "DEBIT",
                "category": "Education",
                "merchant": "SMP Islam Al-Azhar Bekasi",
                "description": "SPP Sekolah Bulanan",
                "channel": "TRANSFER"
            })

        # Utilities
        for u_date in [date(2026, 8, 4), date(2026, 9, 4), date(2026, 10, 4)]:
            txns.append({
                "posted_at": _dt(u_date, 11, 0),
                "amount": _dec(350000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "PLN Persero",
                "description": "Tagihan Listrik PLN Pasca Bayar",
                "channel": "MOBILE_BANKING"
            })
            txns.append({
                "posted_at": _dt(u_date + timedelta(days=6), 11, 30),
                "amount": _dec(150000),
                "direction": "DEBIT",
                "category": "Health",
                "merchant": "BPJS Kesehatan",
                "description": "Iuran BPJS Kesehatan Mandiri",
                "channel": "AUTO_DEBIT"
            })
            txns.append({
                "posted_at": _dt(u_date + timedelta(days=11), 12, 0),
                "amount": _dec(380000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "IndiHome Telkom",
                "description": "Tagihan Internet IndiHome",
                "channel": "MOBILE_BANKING"
            })

        # Weekly Groceries and Dining
        for w in range(12):
            g_date = date(2026, 7, 21) + timedelta(days=w * 7)
            txns.append({
                "posted_at": _dt(g_date, 16, 0),
                "amount": _dec(450000),
                "direction": "DEBIT",
                "category": "Groceries",
                "merchant": "Super Indo Bekasi",
                "description": "Belanja Mingguan Kebutuhan Dapur",
                "channel": "EDC"
            })
            txns.append({
                "posted_at": _dt(g_date + timedelta(days=3), 19, 30),
                "amount": _dec(165000),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Restoran Padang Sederhana",
                "description": "Makan Malam Keluarga",
                "channel": "QRIS"
            })

        net = sum((t["amount"] if t["direction"] == "CREDIT" else -t["amount"]) for t in txns)
        opening_balance = target_final_balance - net
        txns.sort(key=lambda x: x["posted_at"])
        return txns, opening_balance

    # ---------------------------------------------------------
    # Demo Story 2: Aditya Pratama (affluent, engineer)
    # ---------------------------------------------------------
    if cust_key == "ADITYA":
        opening_balance = _dec(385000000)
        # Salary on 25th: 48M IDR
        for s_date in [date(2026, 7, 25), date(2026, 8, 25), date(2026, 9, 25)]:
            txns.append({
                "posted_at": _dt(s_date, 9, 15),
                "amount": _dec(48000000),
                "direction": "CREDIT",
                "category": "Salary",
                "merchant": "PT Tech Inovasi Nusantara",
                "description": "Gaji Bulanan VP Engineering",
                "channel": "TRANSFER"
            })

        # Affluent spend: dining, flights, memberships, utilities
        for m in range(3):
            base_m = date(2026, 8, 1) + timedelta(days=m * 30)
            txns.append({
                "posted_at": _dt(base_m + timedelta(days=2), 12, 0),
                "amount": _dec(4500000),
                "direction": "DEBIT",
                "category": "Travel",
                "merchant": "Garuda Indonesia",
                "description": "Tiket Penerbangan Bisnis Jakarta-Surabaya",
                "channel": "MOBILE_BANKING"
            })
            txns.append({
                "posted_at": _dt(base_m + timedelta(days=8), 20, 0),
                "amount": _dec(2250000),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Plataran Menteng",
                "description": "Fine Dining & Dinner Meeting",
                "channel": "EDC"
            })
            txns.append({
                "posted_at": _dt(base_m + timedelta(days=14), 15, 0),
                "amount": _dec(1850000),
                "direction": "DEBIT",
                "category": "Health",
                "merchant": "Celebrity Fitness Pacific Place",
                "description": "Iuran Bulanan Executive Gym",
                "channel": "AUTO_DEBIT"
            })
            txns.append({
                "posted_at": _dt(base_m + timedelta(days=20), 17, 30),
                "amount": _dec(3800000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "Apartemen Senopati Suites",
                "description": "IPL dan Service Charge Hunian",
                "channel": "TRANSFER"
            })

        txns.sort(key=lambda x: x["posted_at"])
        return txns, opening_balance

    # ---------------------------------------------------------
    # Demo Story 3: Nabila Aulia (freelancer, designer)
    # ---------------------------------------------------------
    if cust_key == "NABILA":
        opening_balance = _dec(4200000)
        # Irregular freelance project fees
        freelance_credits = [
            (date(2026, 7, 22), 8500000, "Studio Desain Grafika", "Pelunasan Invoice Brand Identity UI/UX"),
            (date(2026, 8, 8), 12500000, "PT Cipta Digital Nusantara", "DP Proyek Mobile App Design System"),
            (date(2026, 9, 2), 5000000, "CV Kreasi Visual", "Retainer Bulanan Desain Produk"),
            (date(2026, 10, 6), 9500000, "Studio Web Kreasi", "Pelunasan Website Redesign"),
        ]
        for d, amt, m, desc in freelance_credits:
            txns.append({
                "posted_at": _dt(d, 14, 0),
                "amount": _dec(amt),
                "direction": "CREDIT",
                "category": "Freelance Income",
                "merchant": m,
                "description": desc,
                "channel": "TRANSFER"
            })

        # Rent on 1st of each month (causes low-balance dip before Oct 6 payment)
        for r_date in [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]:
            txns.append({
                "posted_at": _dt(r_date, 10, 0),
                "amount": _dec(3500000),
                "direction": "DEBIT",
                "category": "Rent",
                "merchant": "Apartemen Bintaro Plaza",
                "description": "Sewa Apartemen Studio Bulanan",
                "channel": "TRANSFER"
            })

        # Recurring software and utilities
        for m_idx in range(3):
            m_base = date(2026, 8, 1) + timedelta(days=m_idx * 30)
            txns.append({
                "posted_at": _dt(m_base + timedelta(days=2), 9, 0),
                "amount": _dec(245000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "Figma Inc",
                "description": "Langganan Figma Professional",
                "channel": "AUTO_DEBIT"
            })
            txns.append({
                "posted_at": _dt(m_base + timedelta(days=10), 10, 0),
                "amount": _dec(150000),
                "direction": "DEBIT",
                "category": "Health",
                "merchant": "BPJS Kesehatan",
                "description": "Iuran BPJS Kesehatan",
                "channel": "AUTO_DEBIT"
            })
            txns.append({
                "posted_at": _dt(m_base + timedelta(days=12), 11, 0),
                "amount": _dec(550000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "Adobe Creative Cloud",
                "description": "Langganan Adobe CC All Apps",
                "channel": "AUTO_DEBIT"
            })
            txns.append({
                "posted_at": _dt(m_base + timedelta(days=15), 14, 0),
                "amount": _dec(450000),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "MyRepublic Internet",
                "description": "Internet Fiber Studio",
                "channel": "MOBILE_BANKING"
            })

        # Lifestyle & Work in Cafes
        for w in range(12):
            c_date = date(2026, 7, 23) + timedelta(days=w * 7)
            txns.append({
                "posted_at": _dt(c_date, 15, 30),
                "amount": _dec(120000),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Kopi Kalyan BSD",
                "description": "Kopi & Ruang Kerja Freelance",
                "channel": "QRIS"
            })
            txns.append({
                "posted_at": _dt(c_date + timedelta(days=4), 18, 0),
                "amount": _dec(85000),
                "direction": "DEBIT",
                "category": "Transport",
                "merchant": "Gojek Indonesia",
                "description": "GoRide Transportasi",
                "channel": "QRIS"
            })

        txns.sort(key=lambda x: x["posted_at"])
        return txns, opening_balance

    # ---------------------------------------------------------
    # PT Sinar Distribusi (reserve savings account)
    # ---------------------------------------------------------
    if cust_key == "SINAR":
        opening_balance = _dec(150000000)
        # Occasional transfers between current and savings reserve
        txns.append({
            "posted_at": _dt(date(2026, 8, 15), 14, 0),
            "amount": _dec(25000000),
            "direction": "CREDIT",
            "category": "Transfers",
            "merchant": "Internal Transfer PT Sinar",
            "description": "Pemindahan Surplus Likuiditas ke Tabungan Bisnis",
            "channel": "INTERNET_BANKING"
        })
        txns.append({
            "posted_at": _dt(date(2026, 9, 20), 11, 0),
            "amount": _dec(15000000),
            "direction": "DEBIT",
            "category": "Transfers",
            "merchant": "Internal Transfer PT Sinar",
            "description": "Alokasi Cadangan Operasional ke Giro",
            "channel": "INTERNET_BANKING"
        })
        return txns, opening_balance

    # ---------------------------------------------------------
    # Generic customer transactions driven by persona
    # ---------------------------------------------------------
    rng = random.Random(idx + 1000)
    txns = []

    if persona == "salaried":
        salary_amt = _dec(7000000 + (idx * 500000) % 18000000)
        if segment == "AFFLUENT":
            salary_amt = _dec(35000000 + (idx * 2000000) % 30000000)
        opening_balance = salary_amt * 2

        # Salary credits on 25th
        for s_date in [date(2026, 7, 25), date(2026, 8, 25), date(2026, 9, 25)]:
            txns.append({
                "posted_at": _dt(s_date, 9, 0),
                "amount": salary_amt,
                "direction": "CREDIT",
                "category": "Salary",
                "merchant": f"PT Perusahaan Klien {idx % 20 + 1}",
                "description": "Gaji Bulanan",
                "channel": "TRANSFER"
            })

        # Recurring bills
        for m_idx in range(3):
            b_date = date(2026, 8, 5) + timedelta(days=m_idx * 30)
            txns.append({
                "posted_at": _dt(b_date, 10, 0),
                "amount": _dec(rng.randint(250000, 750000)),
                "direction": "DEBIT",
                "category": "Utilities",
                "merchant": "PLN Persero",
                "description": "Tagihan Listrik",
                "channel": "MOBILE_BANKING"
            })
            txns.append({
                "posted_at": _dt(b_date + timedelta(days=5), 11, 0),
                "amount": _dec(150000),
                "direction": "DEBIT",
                "category": "Health",
                "merchant": "BPJS Kesehatan",
                "description": "Iuran BPJS Kesehatan",
                "channel": "AUTO_DEBIT"
            })

        # General spend
        for w in range(10):
            sp_date = date(2026, 7, 22) + timedelta(days=w * 8 + (idx % 5))
            txns.append({
                "posted_at": _dt(sp_date, 14, 0),
                "amount": _dec(rng.randint(200000, 600000)),
                "direction": "DEBIT",
                "category": "Groceries",
                "merchant": "Alfamart / Indomaret",
                "description": "Belanja Kebutuhan Harian",
                "channel": "QRIS"
            })
            txns.append({
                "posted_at": _dt(sp_date + timedelta(days=2), 19, 0),
                "amount": _dec(rng.randint(75000, 250000)),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Restoran / Cafe",
                "description": "Makan dan Minum",
                "channel": "QRIS"
            })
            txns.append({
                "posted_at": _dt(sp_date + timedelta(days=4), 8, 30),
                "amount": _dec(rng.randint(40000, 150000)),
                "direction": "DEBIT",
                "category": "Transport",
                "merchant": "Gojek / Grab",
                "description": "Transportasi Online",
                "channel": "QRIS"
            })

    elif persona == "freelancer":
        opening_balance = _dec(5000000 + (idx * 300000) % 8000000)
        # Irregular credits
        for f_idx in range(5):
            cr_date = date(2026, 7, 22) + timedelta(days=f_idx * 16 + (idx % 7))
            txns.append({
                "posted_at": _dt(cr_date, 13, 0),
                "amount": _dec(rng.randint(4000000, 12000000)),
                "direction": "CREDIT",
                "category": "Freelance Income",
                "merchant": f"Klien Proyek {f_idx + 1}",
                "description": "Pembayaran Honor Proyek",
                "channel": "TRANSFER"
            })
        # Spend
        for w in range(8):
            sp_date = date(2026, 7, 24) + timedelta(days=w * 10)
            txns.append({
                "posted_at": _dt(sp_date, 15, 0),
                "amount": _dec(rng.randint(150000, 450000)),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Kafe & Resto",
                "description": "Konsumsi dan Ruang Kerja",
                "channel": "QRIS"
            })

    elif persona == "retiree":
        opening_balance = _dec(15000000 + (idx * 500000) % 25000000)
        # Pension credit on 1st of month
        for p_date in [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]:
            txns.append({
                "posted_at": _dt(p_date, 8, 0),
                "amount": _dec(rng.randint(4500000, 8500000)),
                "direction": "CREDIT",
                "category": "Pension",
                "merchant": "PT Taspen Persero",
                "description": "Manfaat Pensiun Bulanan",
                "channel": "TRANSFER"
            })
        # Health & pharmacy
        for m_idx in range(3):
            h_date = date(2026, 8, 12) + timedelta(days=m_idx * 28)
            txns.append({
                "posted_at": _dt(h_date, 10, 0),
                "amount": _dec(rng.randint(350000, 850000)),
                "direction": "DEBIT",
                "category": "Health",
                "merchant": "Apotek Kimia Farma",
                "description": "Pembelian Obat dan Vitamin Rutin",
                "channel": "EDC"
            })

    elif persona == "student":
        opening_balance = _dec(1500000 + (idx * 100000) % 2000000)
        # Allowance
        for a_date in [date(2026, 8, 2), date(2026, 9, 2), date(2026, 10, 2)]:
            txns.append({
                "posted_at": _dt(a_date, 10, 0),
                "amount": _dec(rng.randint(2000000, 3500000)),
                "direction": "CREDIT",
                "category": "Allowance",
                "merchant": "Transfer Orang Tua",
                "description": "Uang Saku dan Kuliah",
                "channel": "TRANSFER"
            })
        # Daily campus spend
        for w in range(12):
            sp_date = date(2026, 7, 21) + timedelta(days=w * 7)
            txns.append({
                "posted_at": _dt(sp_date, 12, 30),
                "amount": _dec(rng.randint(25000, 65000)),
                "direction": "DEBIT",
                "category": "Dining",
                "merchant": "Kantin Kampus",
                "description": "Makan Siang",
                "channel": "QRIS"
            })
            txns.append({
                "posted_at": _dt(sp_date + timedelta(days=2), 17, 0),
                "amount": _dec(rng.randint(20000, 50000)),
                "direction": "DEBIT",
                "category": "Transport",
                "merchant": "KAI / TransJakarta",
                "description": "Transportasi Kampus",
                "channel": "EDC"
            })

    else:  # sme_merchant / corporate savings reserve
        opening_balance = _dec(25000000 + (idx * 1000000) % 50000000)
        txns.append({
            "posted_at": _dt(date(2026, 8, 10), 11, 0),
            "amount": _dec(5000000),
            "direction": "CREDIT",
            "category": "Savings",
            "merchant": "Setoran Tunai",
            "description": "Setoran Tunai Cadangan Usaha",
            "channel": "BRANCH"
        })

    txns.sort(key=lambda x: x["posted_at"])
    return txns, opening_balance


def _generate_current_txns(cust_key: str, persona: str, segment: str, idx: int) -> tuple[list[dict], Decimal]:
    """Generate 90-day transactions and opening balance for a business current account."""
    txns = []

    # ---------------------------------------------------------
    # Demo Story 4: PT Sinar Distribusi (steady SME settlements)
    # ---------------------------------------------------------
    if cust_key == "SINAR":
        opening_balance = _dec(220000000)
        rng_sinar = random.Random(4001)

        # Steady weekday settlements (over ~65 business days)
        cur_d = date(2026, 7, 20)
        while cur_d <= ANCHOR_DATE:
            if cur_d.weekday() < 5:  # Mon to Fri
                settlement_amt = _dec(rng_sinar.randint(4500000, 12000000))
                txns.append({
                    "posted_at": _dt(cur_d, 17, 30),
                    "amount": settlement_amt,
                    "direction": "CREDIT",
                    "category": "Merchant Settlement",
                    "merchant": "Bank Settlement QRIS / EDC",
                    "description": "Penyelesaian Transaksi Penjualan Distribusi Harian",
                    "channel": "SETTLEMENT"
                })
            cur_d += timedelta(days=1)

        # Bi-weekly supplier payments
        for sup_idx in range(6):
            s_d = date(2026, 7, 28) + timedelta(days=sup_idx * 14)
            txns.append({
                "posted_at": _dt(s_d, 11, 0),
                "amount": _dec(rng_sinar.randint(42000000, 68000000)),
                "direction": "DEBIT",
                "category": "Supplier Payment",
                "merchant": "PT Pangan Sumber Makmur",
                "description": "Pembayaran Faktur Bahan Pokok Grosir",
                "channel": "INTERNET_BANKING"
            })

        # Monthly payroll on 28th
        for p_date in [date(2026, 7, 28), date(2026, 8, 28), date(2026, 9, 28)]:
            txns.append({
                "posted_at": _dt(p_date, 10, 0),
                "amount": _dec(32500000),
                "direction": "DEBIT",
                "category": "Payroll",
                "merchant": "Payroll Karyawan Sinar",
                "description": "Gaji Staf Gudang dan Supir Distribusi",
                "channel": "TRANSFER"
            })

        # Warehouse rent and electricity
        for r_date in [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]:
            txns.append({
                "posted_at": _dt(r_date, 14, 0),
                "amount": _dec(12000000),
                "direction": "DEBIT",
                "category": "Rent",
                "merchant": "Kawasan Pergudangan Bekasi",
                "description": "Sewa Gudang Distribusi",
                "channel": "TRANSFER"
            })

        txns.sort(key=lambda x: x["posted_at"])
        return txns, opening_balance

    # ---------------------------------------------------------
    # Generic SME / Corporate current accounts
    # ---------------------------------------------------------
    rng = random.Random(idx + 5000)
    opening_balance = _dec(150000000 if segment == "CORPORATE" else 35000000)

    # Weekly merchant settlements or corporate receivables
    for w in range(12):
        s_date = date(2026, 7, 22) + timedelta(days=w * 7 + (idx % 3))
        cr_amt = _dec(rng.randint(8000000, 25000000) if segment == "SME" else rng.randint(50000000, 150000000))
        txns.append({
            "posted_at": _dt(s_date, 16, 0),
            "amount": cr_amt,
            "direction": "CREDIT",
            "category": "Merchant Settlement",
            "merchant": "Settlement Penjualan",
            "description": "Penyelesaian Transaksi Usaha",
            "channel": "SETTLEMENT"
        })

        db_amt = _dec(rng.randint(5000000, 18000000) if segment == "SME" else rng.randint(35000000, 110000000))
        txns.append({
            "posted_at": _dt(s_date + timedelta(days=3), 11, 0),
            "amount": db_amt,
            "direction": "DEBIT",
            "category": "Supplier Payment",
            "merchant": "Mitra Pemasok Usaha",
            "description": "Pembayaran Faktur Supplier",
            "channel": "INTERNET_BANKING"
        })

    txns.sort(key=lambda x: x["posted_at"])
    return txns, opening_balance
