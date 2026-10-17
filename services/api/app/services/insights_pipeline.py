"""Core-banking financial insights pipeline.

Pure calculations over BankAccount and BankTransaction records for a linked BankCustomer.
All monetary arithmetic uses Decimal with bounded rounding.
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from typing import Optional, Any

from sqlalchemy.orm import Session

from ..models.entities import utc_now
from ..models.banking import BankCustomer, BankAccount, BankTransaction
from ..models.relationships import Party, Source, EngagementFeedback
from .rm import uid, source_data, j
from .money_display import money_text, date_text
from .planning import ESSENTIAL_CATEGORIES, DISCRETIONARY_CATEGORIES, planning_cards, planning_facts, planning_source_payload, unavailable_planning_cards

METHOD = 'FIN-PIPE-1: Verified core-banking transaction features and bounded arithmetic.'
CATEGORY_WEIGHTS: dict[str, Decimal] = {
    'CARE': Decimal('100.00'),
    'GUIDANCE': Decimal('10.00'),
    'EDUCATION': Decimal('3.00'),
    'RECOGNITION': Decimal('2.00'),
    'COMMERCIAL': Decimal('1.00'),
}


def customer_for_party(db: Session, party: Party) -> Optional[BankCustomer]:
    """Finds the BankCustomer row linked to an RM Party."""
    if not party:
        return None
    cust = db.query(BankCustomer).filter_by(
        tenant_id=party.tenant_id,
        party_id=party.id,
    ).first()
    if cust:
        return cust
    if party.customer_ref:
        cust = db.query(BankCustomer).filter_by(
            tenant_id=party.tenant_id,
            cif=party.customer_ref,
        ).first()
        if cust:
            return cust
    return None


def _normalize_dt(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val.replace(tzinfo=None) if val.tzinfo is not None else val
    if isinstance(val, date):
        return datetime.combine(val, datetime.max.time().replace(microsecond=0))
    return utc_now().replace(tzinfo=None)


def features_for(db: Session, customer: BankCustomer, as_of: Optional[Any] = None) -> dict[str, Any]:
    """Pure feature extraction over BankAccount and BankTransaction.
    
    Returns structured features with Decimal values throughout.
    """
    if as_of is None:
        latest_txn = db.query(BankTransaction).filter_by(
            tenant_id=customer.tenant_id,
            customer_id=customer.id,
        ).order_by(BankTransaction.posted_at.desc()).first()
        if latest_txn and latest_txn.posted_at:
            as_of_dt = _normalize_dt(latest_txn.posted_at)
        else:
            as_of_dt = _normalize_dt(utc_now())
    else:
        as_of_dt = _normalize_dt(as_of)

    as_of_date = as_of_dt.date()
    t_30 = as_of_dt - timedelta(days=30)
    t_60 = as_of_dt - timedelta(days=60)
    t_90 = as_of_dt - timedelta(days=90)

    accounts = db.query(BankAccount).filter_by(
        tenant_id=customer.tenant_id,
        customer_id=customer.id,
        status='ACTIVE',
    ).all()

    txns = db.query(BankTransaction).filter(
        BankTransaction.tenant_id == customer.tenant_id,
        BankTransaction.customer_id == customer.id,
        BankTransaction.posted_at <= as_of_dt,
    ).order_by(BankTransaction.posted_at.desc()).all()

    # 1. Accounts & Balance calculations
    liquid_accounts = [a for a in accounts if a.product in ('SAVINGS', 'CURRENT')]
    balance_now = sum((Decimal(str(a.balance)) for a in liquid_accounts), Decimal('0.00'))
    savings_balance = sum((Decimal(str(a.balance)) for a in accounts if a.product == 'SAVINGS'), Decimal('0.00'))

    # Reconstruct 30-day closing balances day by day
    daily_net: dict[date, Decimal] = {}
    for tx in txns:
        tx_dt = _normalize_dt(tx.posted_at)
        if t_30 < tx_dt <= as_of_dt:
            t_date = tx_dt.date()
            amt = Decimal(str(tx.amount))
            direction_mult = Decimal('1.00') if tx.direction == 'CREDIT' else Decimal('-1.00')
            daily_net[t_date] = daily_net.get(t_date, Decimal('0.00')) + amt * direction_mult

    daily_balances: list[Decimal] = []
    curr_b = balance_now
    for day_offset in range(30):
        target_d = as_of_date - timedelta(days=day_offset)
        daily_balances.append(curr_b)
        net_on_target = daily_net.get(target_d, Decimal('0.00'))
        curr_b = curr_b - net_on_target

    balance_30d_min = min(daily_balances) if daily_balances else balance_now
    balance_30d_avg = (sum(daily_balances) / Decimal(len(daily_balances))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if daily_balances else balance_now

    # 2. Spend by category with prior-period delta and %
    cat_30: dict[str, Decimal] = {}
    cat_prior: dict[str, Decimal] = {}
    cat_60: dict[str, Decimal] = {}
    cat_90: dict[str, Decimal] = {}
    cat_count_30: dict[str, int] = {}
    tx_ids_30: list[str] = []

    for tx in txns:
        if tx.direction != 'DEBIT':
            continue
        tx_dt = _normalize_dt(tx.posted_at)
        amt = Decimal(str(tx.amount))
        cat = tx.category or 'General'

        if t_30 < tx_dt <= as_of_dt:
            cat_30[cat] = cat_30.get(cat, Decimal('0.00')) + amt
            cat_count_30[cat] = cat_count_30.get(cat, 0) + 1
            tx_ids_30.append(tx.id)
        elif t_60 < tx_dt <= t_30:
            cat_prior[cat] = cat_prior.get(cat, Decimal('0.00')) + amt

        if t_60 < tx_dt <= as_of_dt:
            cat_60[cat] = cat_60.get(cat, Decimal('0.00')) + amt
        if t_90 < tx_dt <= as_of_dt:
            cat_90[cat] = cat_90.get(cat, Decimal('0.00')) + amt

    total_debit_30 = sum(cat_30.values(), Decimal('0.00'))
    total_debit_90 = sum(cat_90.values(), Decimal('0.00'))

    cat_analysis: dict[str, dict[str, Any]] = {}
    all_categories = sorted(set(cat_30.keys()) | set(cat_prior.keys()))
    for cat in all_categories:
        c_amt = cat_30.get(cat, Decimal('0.00'))
        p_amt = cat_prior.get(cat, Decimal('0.00'))
        delta = c_amt - p_amt
        pct = ((delta / p_amt) * Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if p_amt > Decimal('0.00') else None
        cat_analysis[cat] = {
            'current': c_amt,
            'previous': p_amt,
            'delta': delta,
            'change_percent': pct,
            'count_30': cat_count_30.get(cat, 0),
        }

    # Pick focus category: largest positive change or largest current spend
    focus_category = 'Transport'
    increasing_cats = [c for c, data in cat_analysis.items() if data['delta'] > Decimal('0.00')]
    if increasing_cats:
        increasing_cats.sort(key=lambda c: cat_analysis[c]['delta'], reverse=True)
        focus_category = increasing_cats[0]
    elif cat_30:
        sorted_by_spend = sorted(cat_30.keys(), key=lambda c: cat_30[c], reverse=True)
        focus_category = sorted_by_spend[0]
    elif all_categories:
        focus_category = all_categories[0]

    focus_data = cat_analysis.get(focus_category, {
        'current': Decimal('0.00'),
        'previous': Decimal('0.00'),
        'delta': Decimal('0.00'),
        'change_percent': None,
        'count_30': 0,
    })

    # 3. Income regularity and salary detection
    credits_90 = [tx for tx in txns if tx.direction == 'CREDIT' and t_90 < _normalize_dt(tx.posted_at) <= as_of_dt]
    total_credits_90 = sum((Decimal(str(tx.amount)) for tx in credits_90), Decimal('0.00'))
    avg_monthly_income = (total_credits_90 / Decimal('3.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    salary_keywords = ('salary', 'payroll', 'wage', 'honorarium', 'gaji', 'upah')
    salary_candidates = [
        tx for tx in credits_90
        if any(kw in (tx.category or '').lower() or kw in (tx.description or '').lower() or kw in (tx.merchant or '').lower() for kw in salary_keywords)
    ]

    salary_detected = False
    salary_amount = Decimal('0.00')
    salary_day: Optional[int] = None
    is_regular_salary = False

    if salary_candidates:
        salary_candidates.sort(key=lambda tx: _normalize_dt(tx.posted_at), reverse=True)
        latest_sal = salary_candidates[0]
        salary_amount = Decimal(str(latest_sal.amount))
        salary_day = _normalize_dt(latest_sal.posted_at).day
        salary_detected = True
        is_regular_salary = len(salary_candidates) >= 2
    else:
        # Check recurring monthly inflow >= 2M around same day of month (+/- 3 days)
        large_credits = [tx for tx in credits_90 if Decimal(str(tx.amount)) >= Decimal('2000000.00')]
        day_buckets: dict[int, list[BankTransaction]] = {}
        for tx in large_credits:
            d = _normalize_dt(tx.posted_at).day
            placed = False
            for bucket_day in list(day_buckets.keys()):
                if abs(d - bucket_day) <= 3:
                    day_buckets[bucket_day].append(tx)
                    placed = True
                    break
            if not placed:
                day_buckets[d] = [tx]
        for b_day, tx_group in day_buckets.items():
            if len(tx_group) >= 2:
                salary_detected = True
                is_regular_salary = True
                salary_amount = Decimal(str(tx_group[0].amount))
                salary_day = b_day
                break

    # 4. Recurring bills detection
    merchant_txs: dict[str, list[BankTransaction]] = {}
    for tx in txns:
        if tx.direction != 'DEBIT' or not tx.merchant:
            continue
        tx_dt = _normalize_dt(tx.posted_at)
        if t_90 < tx_dt <= as_of_dt:
            merchant_txs.setdefault(tx.merchant, []).append(tx)

    recurring_bills: list[dict[str, Any]] = []
    recurring_cats = {'utilities', 'subscription', 'insurance', 'telecom', 'education', 'rent', 'bills', 'tagihan'}
    for merchant, m_list in merchant_txs.items():
        m_list.sort(key=lambda t: _normalize_dt(t.posted_at))
        is_known_rec_cat = any((t.category or '').lower() in recurring_cats for t in m_list)
        is_known_rec_merchant = any(kw in merchant.lower() for kw in ('pln', 'bpjs', 'telkom', 'indihome', 'netflix', 'spotify', 'pdam'))
        has_multiple = len(m_list) >= 2

        if has_multiple or is_known_rec_cat or is_known_rec_merchant:
            amounts = [Decimal(str(t.amount)) for t in m_list]
            avg_bill_amt = (sum(amounts) / Decimal(len(amounts))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            latest_tx_date = _normalize_dt(m_list[-1].posted_at).date()
            next_date = latest_tx_date + timedelta(days=30)
            while next_date < as_of_date - timedelta(days=5):
                next_date += timedelta(days=30)
            recurring_bills.append({
                'merchant': merchant,
                'category': m_list[-1].category or 'Recurring',
                'amount': avg_bill_amt,
                'monthly_estimate': (sum(amounts) / Decimal('3.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'count_90': len(m_list),
                'cadence': 'MONTHLY',
                'last_date': latest_tx_date,
                'next_expected_date': next_date,
            })

    total_recurring_monthly = sum((b['amount'] for b in recurring_bills), Decimal('0.00'))

    # 5. Idle cash: savings balance above 3x average monthly outflow
    monthly_outflow = (total_debit_90 / Decimal('3.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if total_debit_90 == Decimal('0.00'):
        monthly_outflow = total_debit_30
    idle_threshold = Decimal('3.00') * monthly_outflow
    if monthly_outflow > Decimal('0.00') and savings_balance > idle_threshold:
        idle_cash = savings_balance - idle_threshold
        has_idle_cash = True
    else:
        idle_cash = Decimal('0.00')
        has_idle_cash = False

    # 6. Upcoming commitments in next 14 days vs available balance
    commitments_14d = Decimal('0.00')
    upcoming_bill_items: list[dict[str, Any]] = []
    fourteen_days_ahead = as_of_date + timedelta(days=14)
    for b in recurring_bills:
        if as_of_date <= b['next_expected_date'] <= fourteen_days_ahead:
            commitments_14d += b['amount']
            upcoming_bill_items.append(b)

    cash_flow_diff = balance_now - commitments_14d
    has_cash_gap = cash_flow_diff < Decimal('0.00')

    # 7. Term deposit maturity within 30 days
    maturing_td: Optional[dict[str, Any]] = None
    for a in accounts:
        if a.product == 'TERM_DEPOSIT' and a.maturity_date:
            days_left = (a.maturity_date - as_of_date).days
            if 0 <= days_left <= 30:
                maturing_td = {
                    'account_id': a.id,
                    'account_masked': a.account_masked,
                    'balance': Decimal(str(a.balance)),
                    'maturity_date': a.maturity_date.isoformat(),
                    'days_to_maturity': days_left,
                }
                break

    return {
        'as_of': as_of_dt,
        'as_of_date': as_of_date,
        'currency': 'IDR',
        'balance_now': balance_now,
        'balance_30d_avg': balance_30d_avg,
        'balance_30d_min': balance_30d_min,
        'savings_balance': savings_balance,
        'monthly_outflow': monthly_outflow,
        'total_debit_30': total_debit_30,
        'total_debit_90': total_debit_90,
        'category_analysis': cat_analysis,
        'focus_category': focus_category,
        'focus_spend': focus_data,
        'salary_detected': salary_detected,
        'is_regular_salary': is_regular_salary,
        'salary_amount': salary_amount,
        'salary_day': salary_day,
        'avg_monthly_income': avg_monthly_income,
        'recurring_bills': recurring_bills,
        'total_recurring_monthly': total_recurring_monthly,
        'idle_cash': idle_cash,
        'has_idle_cash': has_idle_cash,
        'commitments_14d': commitments_14d,
        'upcoming_bill_items': upcoming_bill_items,
        'cash_flow_diff': cash_flow_diff,
        'has_cash_gap': has_cash_gap,
        'maturing_td': maturing_td,
        'has_maturing_td': maturing_td is not None,
        'tx_ids_30_count': len(tx_ids_30),
        'balance_30d_ago': balance_now - sum(daily_net.values(), Decimal('0.00')),
        'planning': planning_facts(db, customer, as_of_date),
    }


def serialize_features_for_source(features: dict[str, Any]) -> dict[str, Any]:
    """Prepares JSON-serializable feature payload for the Source row."""
    as_of_dt: datetime = features['as_of']
    focus = features['focus_spend']
    return {
        'complete': True,
        'currency': features['currency'],
        'available': format(features['balance_now'], '.2f'),
        'commitments': format(features['commitments_14d'], '.2f'),
        'period_start': (as_of_dt - timedelta(days=30)).date().isoformat(),
        'period_end': as_of_dt.date().isoformat(),
        'previous_period_start': (as_of_dt - timedelta(days=60)).date().isoformat(),
        'previous_period_end': (as_of_dt - timedelta(days=30)).date().isoformat(),
        'previous_days': 30,
        'current_days': 30,
        'previous_spend': format(focus['previous'], '.2f'),
        'current_spend': format(focus['current'], '.2f'),
        'category': features['focus_category'],
        'recurring_charge': format(features['total_recurring_monthly'], '.2f'),
        'recurring_verified': len(features['recurring_bills']) > 0,
        'planning': planning_source_payload(features['planning']),
        'features': {
            'balance_now': format(features['balance_now'], '.2f'),
            'balance_30d_avg': format(features['balance_30d_avg'], '.2f'),
            'balance_30d_min': format(features['balance_30d_min'], '.2f'),
            'savings_balance': format(features['savings_balance'], '.2f'),
            'monthly_outflow': format(features['monthly_outflow'], '.2f'),
            'idle_cash': format(features['idle_cash'], '.2f'),
            'has_idle_cash': features['has_idle_cash'],
            'salary_detected': features['salary_detected'],
            'is_regular_salary': features['is_regular_salary'],
            'salary_amount': format(features['salary_amount'], '.2f'),
            'salary_day': features['salary_day'],
            'avg_monthly_income': format(features['avg_monthly_income'], '.2f'),
            'recurring_count': len(features['recurring_bills']),
            'commitments_14d': format(features['commitments_14d'], '.2f'),
            'cash_flow_diff': format(features['cash_flow_diff'], '.2f'),
            'has_cash_gap': features['has_cash_gap'],
            'has_maturing_td': features['has_maturing_td'],
            'maturing_td': (
                {
                    'account_masked': features['maturing_td']['account_masked'],
                    'balance': format(features['maturing_td']['balance'], '.2f'),
                    'maturity_date': features['maturing_td']['maturity_date'],
                    'days_to_maturity': features['maturing_td']['days_to_maturity'],
                }
                if features['maturing_td']
                else None
            ),
        },
    }


def refresh_bank_data_source(db: Session, party: Party, features: dict[str, Any], as_of_dt: datetime) -> Source:
    """Creates or refreshes the BANK_DATA_SUMMARY Source row for this party."""
    payload = serialize_features_for_source(features)
    content = json.dumps(payload, ensure_ascii=False)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    s = db.query(Source).filter_by(
        tenant_id=party.tenant_id,
        party_id=party.id,
        kind='BANK_DATA_SUMMARY',
    ).first()

    if s:
        if s.content != content or s.content_hash != content_hash:
            s.content = content
            s.content_hash = content_hash
            s.version = (s.version or 1) + 1
        s.event_at = utc_now()
        db.flush()
        return s

    s = Source(
        id=uid('BANK-SUMMARY'),
        tenant_id=party.tenant_id,
        party_id=party.id,
        kind='BANK_DATA_SUMMARY',
        title='Core-banking financial summary',
        content=content,
        content_hash=content_hash,
        mode='SIMULATED' if json.loads(party.context_json or '{}').get('mode') == 'SYNTHETIC' else 'LIVE',
        event_at=utc_now(),
        version=1,
    )
    db.add(s)
    db.flush()
    return s


def unavailable_cards(source: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Returns standard UNAVAILABLE cards when bank data is unlinked or incomplete."""
    base = {
        'currency': None,
        'values': {},
        'source': source,
        'method': METHOD,
        'status': 'UNAVAILABLE',
    }
    return [
        {**base, 'key': 'cash_flow', 'kind': 'CASH_FLOW', 'title': 'Upcoming commitments', 'explanation': 'Core-banking account coverage is unavailable.'},
        {**base, 'key': 'spending', 'kind': 'SPENDING', 'title': 'Spending comparison', 'explanation': 'Comparable core-banking activity is unavailable.'},
        {**base, 'key': 'recurring', 'kind': 'RECURRING_BILLS', 'title': 'Recurring charge', 'explanation': 'Verified recurring-charge patterns are unavailable.'},
        {**base, 'key': 'salary', 'kind': 'SALARY_INCOME', 'title': 'Income regularity & salary', 'explanation': 'Income and payroll data are unavailable.'},
        {**base, 'key': 'idle_cash', 'kind': 'IDLE_CASH', 'title': 'Surplus liquidity & idle cash', 'explanation': 'Savings and outflow data are unavailable.'},
        {**base, 'key': 'term_deposit', 'kind': 'TERM_DEPOSIT_MATURITY', 'title': 'Term deposit maturity', 'explanation': 'Term deposit records are unavailable.'},
        {**base, 'key': 'balance_trend', 'kind': 'BALANCE_TREND', 'title': '30-day balance trend', 'explanation': 'Balance history is unavailable.'},
    ] + unavailable_planning_cards(source)


def insight_cards(db: Session, party: Party, as_of: Optional[Any] = None) -> list[dict[str, Any]]:
    """Builds insight cards for a party from core-banking data."""
    cust = customer_for_party(db, party)
    if not cust:
        return unavailable_cards()

    features = features_for(db, cust, as_of)
    as_of_dt = features['as_of']
    source_row = refresh_bank_data_source(db, party, features, as_of_dt)
    src_data = source_data(source_row)
    cur = features['currency']

    # 1. Cash flow card
    avail = features['balance_now']
    comm = features['commitments_14d']
    diff = features['cash_flow_diff']
    cash_status = 'GAP' if features['has_cash_gap'] else 'AVAILABLE'
    cash_flow_card = {
        'key': 'cash_flow',
        'kind': 'CASH_FLOW',
        'title': 'Upcoming commitments',
        'currency': cur,
        'status': cash_status,
        'values': {
            'available': format(avail, '.2f'),
            'commitments': format(comm, '.2f'),
            'difference': format(diff, '.2f'),
        },
        'explanation': (
            f"Snapshot available funds of {money_text(avail, cur)} minus supplied upcoming commitments: "
            f"{money_text(diff, cur)}. This is not confirmed disposable or investable surplus."
        ),
        'evidence': {
            'commitments_count': len(features['upcoming_bill_items']),
            'period': '14 days',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 2. Spending card
    focus_cat = features['focus_category']
    focus = features['focus_spend']
    spend_values = {
        'previous_spend': format(focus['previous'], '.2f'),
        'current_spend': format(focus['current'], '.2f'),
        'change': format(focus['delta'], '.2f'),
    }
    if focus['change_percent'] is not None:
        spend_values['change_percent'] = format(focus['change_percent'], '.2f')

    spend_explanation = (
        f"Comparable 30-day periods; category attribution remains correctable. No purchase intent is inferred."
    )
    # Check category correction feedback
    correction = db.query(EngagementFeedback).filter_by(
        tenant_id=party.tenant_id,
        party_id=party.id,
        action='CATEGORY_CORRECTION',
    ).order_by(EngagementFeedback.created_at.desc()).first()
    if correction:
        try:
            cor_data = json.loads(correction.result_json)
            if cor_data.get('source_id') == source_row.id and cor_data.get('source_hash') == source_row.content_hash:
                spend_explanation += f" Customer-provided category correction: {cor_data['category']}. Original attribution is retained."
        except (ValueError, TypeError):
            pass

    spending_card = {
        'key': 'spending',
        'kind': 'SPENDING',
        'title': f"{focus_cat} spending",
        'currency': cur,
        'status': 'AVAILABLE',
        'values': spend_values,
        'explanation': spend_explanation,
        'evidence': {
            'transaction_count': focus['count_30'],
            'period': '30 days vs prior 30 days',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 3. Recurring charge card
    rec_count = len(features['recurring_bills'])
    recurring_total = features['total_recurring_monthly']
    kind_of = lambda category: 'Discretionary' if (category or '').lower() in DISCRETIONARY_CATEGORIES else 'Essential' if (category or '').lower() in ESSENTIAL_CATEGORIES else 'Variable'
    recurring_rows = [
        {'label': b['merchant'], 'category': b['category'], 'type': kind_of(b['category']), 'monthly_estimate': money_text(b['monthly_estimate'], cur),
         'typical_amount': money_text(b['amount'], cur), 'times_90d': str(b['count_90']), 'next_expected': date_text(b['next_expected_date'].isoformat())}
        for b in sorted(features['recurring_bills'], key=lambda b: b['monthly_estimate'], reverse=True)[:12]
    ]
    recurring_values = {
        'amount': format(recurring_total, '.2f'), 'merchant_count': str(rec_count),
        'discretionary_total': format(sum((b['monthly_estimate'] for b in features['recurring_bills'] if kind_of(b['category']) == 'Discretionary'), Decimal('0.00')), '.2f'),
    }
    recurring_card = {
        'key': 'recurring',
        'kind': 'RECURRING_BILLS',
        'title': 'Recurring charge snapshot',
        'currency': cur,
        'status': 'AVAILABLE' if rec_count > 0 else 'UNAVAILABLE',
        'values': recurring_values if rec_count > 0 else {},
        'rows': recurring_rows,
        'explanation': (
            f"Verified pattern in the supplied snapshot ({rec_count} merchant pattern(s)). No cancellation or payment is made."
            if rec_count > 0
            else 'Verified recurring pattern is unavailable.'
        ),
        'evidence': {
            'merchants': [b['merchant'] for b in features['recurring_bills']],
            'period': '90 days',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 4. Salary & income card
    sal_detected = features['salary_detected']
    sal_values = {}
    if sal_detected and features['salary_day']:
        sal_values = {
            'salary_amount': format(features['salary_amount'], '.2f'),
            'salary_day': str(features['salary_day']),
        }
        sal_exp = f"Salary credit of {money_text(features['salary_amount'], cur)} detected monthly around day {features['salary_day']}."
    else:
        sal_values = {'average_monthly': format(features['avg_monthly_income'], '.2f')}
        sal_exp = f"Income regularity: average monthly inflow of {money_text(features['avg_monthly_income'], cur)} across 90 days."

    salary_card = {
        'key': 'salary',
        'kind': 'SALARY_INCOME',
        'title': 'Income regularity & salary',
        'currency': cur,
        'status': 'AVAILABLE' if sal_detected or features['avg_monthly_income'] > Decimal('0.00') else 'UNAVAILABLE',
        'values': sal_values,
        'explanation': sal_exp,
        'evidence': {
            'frequency': 'MONTHLY' if sal_detected else 'IRREGULAR',
            'period': '90 days',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 5. Idle cash card
    idle_amt = features['idle_cash']
    has_idle = features['has_idle_cash']
    idle_values = {}
    if has_idle:
        idle_values = {
            'idle_cash': format(idle_amt, '.2f'),
            'savings_balance': format(features['savings_balance'], '.2f'),
            'monthly_outflow': format(features['monthly_outflow'], '.2f'),
        }
        idle_exp = (
            f"Savings balance of {money_text(features['savings_balance'], cur)} exceeds 3x monthly outflow "
            f"({money_text(Decimal('3.00') * features['monthly_outflow'], cur)}) by {money_text(idle_amt, cur)}."
        )
    else:
        idle_exp = "Savings balance does not exceed 3x average monthly outflow."

    idle_cash_card = {
        'key': 'idle_cash',
        'kind': 'IDLE_CASH',
        'title': 'Surplus liquidity & idle cash',
        'currency': cur,
        'status': 'AVAILABLE' if has_idle else 'UNAVAILABLE',
        'values': idle_values,
        'explanation': idle_exp,
        'evidence': {
            'multiplier': '3x',
            'period': '90 days outflow',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 6. Term deposit card
    td = features['maturing_td']
    td_values = {}
    if td:
        td_values = {
            'balance': format(td['balance'], '.2f'),
            'maturity_date': td['maturity_date'],
            'days_to_maturity': str(td['days_to_maturity']),
        }
        td_exp = (
            f"Term deposit of {money_text(td['balance'], cur)} matures on {date_text(td['maturity_date'])} "
            f"({td['days_to_maturity']} days remaining)."
        )
    else:
        td_exp = "No term deposit maturing within the next 30 days."

    td_card = {
        'key': 'term_deposit',
        'kind': 'TERM_DEPOSIT_MATURITY',
        'title': 'Term deposit maturity',
        'currency': cur,
        'status': 'AVAILABLE' if td else 'UNAVAILABLE',
        'values': td_values,
        'explanation': td_exp,
        'evidence': {
            'account_masked': td['account_masked'] if td else None,
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    # 7. Balance trend card
    balance_trend_card = {
        'key': 'balance_trend',
        'kind': 'BALANCE_TREND',
        'title': '30-day balance trend',
        'currency': cur,
        'status': 'AVAILABLE',
        'values': {
            'balance_now': format(avail, '.2f'),
            'balance_30d_avg': format(features['balance_30d_avg'], '.2f'),
            'balance_30d_min': format(features['balance_30d_min'], '.2f'),
        },
        'explanation': (
            f"Current balance is {money_text(avail, cur)} with 30-day average of "
            f"{money_text(features['balance_30d_avg'], cur)} and minimum of {money_text(features['balance_30d_min'], cur)}."
        ),
        'evidence': {
            'period': '30 days',
            'method': 'FIN-PIPE-1',
        },
        'source': src_data,
        'method': METHOD,
    }

    return [
        cash_flow_card,
        spending_card,
        recurring_card,
        salary_card,
        idle_cash_card,
        td_card,
        balance_trend_card,
    ] + planning_cards(features, src_data, cur)


def score_candidate(
    category: str,
    magnitude_val: Decimal | float,
    recency_days: int = 0,
    is_urgent_care: bool = False,
) -> Decimal:
    """Calculates deterministic nudge candidate score.
    
    Formula: score = category_base_weight * normalized_magnitude * recency
    Care first: CARE (100.0) strictly dominates commercial (1.0).
    """
    base_weight = CATEGORY_WEIGHTS.get(category, Decimal('1.00'))
    try:
        mag = Decimal(str(magnitude_val))
    except (InvalidOperation, ValueError, TypeError):
        mag = Decimal('0.50')

    # Normalize magnitude to [0.10, 1.00]
    norm_mag = min(Decimal('1.00'), max(Decimal('0.10'), mag))

    # Recency factor in [0.10, 1.00]
    rec_days = max(0, recency_days)
    recency_factor = max(Decimal('0.10'), Decimal('1.00') - (Decimal(rec_days) / Decimal('30.00')))
    if is_urgent_care:
        recency_factor = Decimal('1.00')

    score = (base_weight * norm_mag * recency_factor).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    return score
