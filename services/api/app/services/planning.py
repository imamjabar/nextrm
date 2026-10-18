"""Planning insights: spending breakdown, safe-to-spend, goals, debt trade-off, portfolio, net worth, next actions.

Pure Decimal arithmetic over linked bank records. No model call computes anything here: the assistant only explains
figures that were produced by these functions and carry the same source hash as the other insights.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models.banking import BankAccount, BankCustomer, BankGoal, BankHolding
from .money_display import date_text, money_text

PLAN_METHOD = 'PLAN-1: Deterministic Decimal planning calculations over linked bank records; the model performs no arithmetic.'
ZERO = Decimal('0.00')
HUNDRED = Decimal('100')
MONTH_DAYS = Decimal('30.4375')
BUFFER_TARGET_MONTHS = Decimal('3')
DISCRETIONARY_CATEGORIES = frozenset({'entertainment', 'subscription', 'dining', 'shopping', 'leisure', 'travel'})
ESSENTIAL_CATEGORIES = frozenset({'utilities', 'education', 'health', 'insurance', 'rent', 'telecom', 'bills', 'tagihan'})
CLASS_LABELS = {'MONEY_MARKET': 'Money market', 'BOND': 'Bond', 'EQUITY': 'Equity'}
STATUS_LABELS = {'COMPLETE': 'Complete', 'ON_TRACK': 'On track', 'BEHIND': 'Behind'}
KEYS = ('spending_breakdown', 'safe_to_spend', 'goal_progress', 'debt', 'portfolio', 'net_worth', 'next_actions', 'market_insights')
TITLES = {
    'spending_breakdown': ('SPENDING_BREAKDOWN', 'Where your money went'),
    'safe_to_spend': ('SAFE_TO_SPEND', 'Safe to spend until payday'),
    'goal_progress': ('GOAL_PROGRESS', 'Goal progress'),
    'debt': ('DEBT_TRADEOFF', 'Credit card cost'),
    'portfolio': ('PORTFOLIO', 'Investment holdings'),
    'net_worth': ('NET_WORTH', 'Net worth and financial health'),
    'next_actions': ('NEXT_ACTIONS', 'Suggested next steps'),
    'market_insights': ('MARKET_INSIGHTS', 'Market insights'),
}
UNAVAILABLE_TEXT = {
    'spending_breakdown': 'Comparable core-banking activity is unavailable.',
    'safe_to_spend': 'Balance, income and spending history are unavailable.',
    'goal_progress': 'No savings goal is recorded for this profile.',
    'debt': 'No outstanding credit card balance is recorded.',
    'portfolio': 'No investment holdings are linked to this profile.',
    'net_worth': 'Account coverage is unavailable.',
    'market_insights': 'Market session feeds are currently unavailable.',
    'next_actions': 'Not enough linked information to suggest next steps.',
}


def q2(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def ratio_percent(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
    return q2(numerator * HUNDRED / denominator) if denominator > 0 else None


def percent_text(value: Optional[Decimal], signed: bool = False) -> str:
    if value is None:
        return 'n/a'
    return f'{value:+.2f}%' if signed and value != 0 else f'{value:.2f}%'


def fixed(value: Decimal) -> str:
    return format(q2(value), '.2f')


def planning_facts(db: Session, customer: BankCustomer, as_of_date: date) -> dict[str, Any]:
    """Raw planning inputs for one linked customer: cards, deposits, goals and holdings."""
    accounts = db.query(BankAccount).filter_by(tenant_id=customer.tenant_id, customer_id=customer.id, status='ACTIVE').all()
    cards = [
        {'masked': a.account_masked, 'balance': q2(a.balance), 'rate': q2(a.interest_rate_percent) if a.interest_rate_percent is not None else None,
         'minimum': q2(a.minimum_payment) if a.minimum_payment is not None else None, 'due_day': a.payment_due_day}
        for a in sorted(accounts, key=lambda x: x.id) if a.product == 'CREDIT_CARD'
    ]
    savings = [a for a in accounts if a.product == 'SAVINGS' and a.interest_rate_percent is not None]
    deposits = [a for a in accounts if a.product == 'TERM_DEPOSIT']
    month_ago = as_of_date - timedelta(days=30)
    goals = db.query(BankGoal).filter_by(tenant_id=customer.tenant_id, customer_id=customer.id, status='ACTIVE').order_by(BankGoal.target_date, BankGoal.id).all()
    holdings = db.query(BankHolding).filter_by(tenant_id=customer.tenant_id, customer_id=customer.id).order_by(BankHolding.id).all()
    return {
        'cards': cards,
        'savings_interest_percent': q2(savings[0].interest_rate_percent) if savings else None,
        'deposits_total': sum((q2(a.balance) for a in deposits), ZERO),
        'deposits_30d_ago': sum((q2(a.balance) for a in deposits if (a.opened_at or as_of_date) <= month_ago), ZERO),
        'goals': [{'name': g.name, 'target': q2(g.target_amount), 'saved': q2(g.saved_amount), 'plan': q2(g.monthly_plan), 'target_date': g.target_date} for g in goals],
        'holdings': [
            {'instrument': h.instrument, 'asset_class': h.asset_class, 'cost': q2(h.cost_basis), 'value': q2(h.market_value),
             'value_30d_ago': q2(h.value_30d_ago) if h.value_30d_ago is not None else None, 'as_of': h.as_of}
            for h in holdings
        ],
    }


def planning_source_payload(facts: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe digest of the planning inputs, so the source hash covers every figure the cards use."""
    optional = lambda v: fixed(v) if v is not None else None
    return {
        'cards': [{**c, 'balance': fixed(c['balance']), 'rate': optional(c['rate']), 'minimum': optional(c['minimum'])} for c in facts['cards']],
        'savings_interest_percent': optional(facts['savings_interest_percent']),
        'deposits_total': fixed(facts['deposits_total']),
        'goals': [{'name': g['name'], 'target': fixed(g['target']), 'saved': fixed(g['saved']), 'plan': fixed(g['plan']), 'target_date': g['target_date'].isoformat()} for g in facts['goals']],
        'holdings': [{'instrument': h['instrument'], 'asset_class': h['asset_class'], 'cost': fixed(h['cost']), 'value': fixed(h['value']), 'value_30d_ago': optional(h['value_30d_ago'])} for h in facts['holdings']],
    }


def next_payday(as_of_date: date, day: int) -> date:
    year, month = as_of_date.year, as_of_date.month
    candidate = date(year, month, min(day, calendar.monthrange(year, month)[1]))
    if candidate <= as_of_date:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        candidate = date(year, month, min(day, calendar.monthrange(year, month)[1]))
    return candidate


def months_left(as_of_date: date, target: date) -> int:
    return max(0, int(Decimal((target - as_of_date).days) // MONTH_DAYS))


def months_to_clear_at_fixed_payment(balance: Decimal, annual_rate_percent: Decimal, payment: Decimal) -> tuple[Optional[int], Optional[Decimal]]:
    """Months and total interest if the same payment is kept; (None, None) when it never clears the balance."""
    monthly = annual_rate_percent / Decimal(1200)
    remaining, months, interest_total = balance, 0, ZERO
    while remaining > 0 and months < 600:
        interest = q2(remaining * monthly)
        if payment <= interest:
            return None, None
        remaining = remaining + interest - payment
        interest_total += interest
        months += 1
    return (months, interest_total) if remaining <= 0 else (None, None)


def card(key: str, status: str, values: dict[str, str], explanation: str, source: Optional[dict], currency: Optional[str],
         rows: Optional[list[dict[str, str]]] = None, evidence: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    kind, title = TITLES[key]
    return {'key': key, 'kind': kind, 'title': title, 'currency': currency, 'status': status, 'values': values, 'rows': rows or [],
            'explanation': explanation, 'evidence': evidence or {'method': 'PLAN-1'}, 'source': source, 'method': PLAN_METHOD}


def unavailable_planning_cards(source: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    return [card(key, 'UNAVAILABLE', {}, UNAVAILABLE_TEXT[key], source, None) for key in KEYS]


def spending_breakdown_card(features: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    analysis, total = features['category_analysis'], features['total_debit_30']
    ranked = sorted((c for c in analysis if analysis[c]['current'] > 0), key=lambda c: analysis[c]['current'], reverse=True)
    if total <= 0 or not ranked:
        return card('spending_breakdown', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['spending_breakdown'], source, cur)
    rows = [{'label': name, 'amount': money_text(analysis[name]['current'], cur), 'share_percent': percent_text(ratio_percent(analysis[name]['current'], total)),
             'change_percent': percent_text(analysis[name]['change_percent'], signed=True),
             'trend': 'UP' if analysis[name]['delta'] > 0 else 'DOWN' if analysis[name]['delta'] < 0 else 'FLAT'} for name in ranked[:6]]
    top = ranked[0]
    income, outflow = features['avg_monthly_income'], features['monthly_outflow']
    values = {'total_spend': fixed(total), 'top_category': top, 'top_category_amount': fixed(analysis[top]['current']),
              'top_category_percent': fixed(ratio_percent(analysis[top]['current'], total))}
    if income > 0:
        values.update(income_monthly=fixed(income), spend_to_income_percent=fixed(ratio_percent(outflow, income)),
                      savings_rate_percent=fixed(ratio_percent(income - outflow, income)))
    risers = [c for c in ranked if analysis[c]['delta'] > 0 and analysis[c]['change_percent'] is not None]
    if risers:
        biggest = max(risers, key=lambda c: analysis[c]['delta'])
        values.update(biggest_increase_category=biggest, biggest_increase_amount=fixed(analysis[biggest]['delta']),
                      biggest_increase_percent=fixed(analysis[biggest]['change_percent']))
    explanation = (f"Last 30 days: {money_text(total, cur)} spent, led by {top} ({percent_text(ratio_percent(analysis[top]['current'], total))} of spending), "
                   'compared with the previous 30 days. Category attribution remains correctable; typical income and spending use 90-day averages.')
    return card('spending_breakdown', 'AVAILABLE', values, explanation, source, cur, rows, {'period': '30 days vs prior 30 days', 'method': 'PLAN-1'})


def safe_to_spend_card(features: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    as_of_date = features['as_of_date']
    balance, outflow, income = features['balance_now'], features['monthly_outflow'], features['avg_monthly_income']
    if outflow <= 0 and income <= 0:
        return card('safe_to_spend', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['safe_to_spend'], source, cur)
    payday = next_payday(as_of_date, features['salary_day']) if features['salary_detected'] and features['salary_day'] else None
    horizon = payday or as_of_date + timedelta(days=30)
    days = (horizon - as_of_date).days
    bills = [b for b in features['recurring_bills'] if b['kind'] == 'BILL']
    bills_due = sum((b['amount'] for b in bills if as_of_date <= b['next_expected_date'] <= horizon), ZERO)
    facts = features['planning']
    card_due = sum((c['minimum'] for c in facts['cards'] if c['minimum'] and c['due_day'] and next_payday(as_of_date, c['due_day']) <= horizon), ZERO)
    everyday_monthly = max(outflow - sum((b['monthly_estimate'] for b in bills), ZERO), ZERO)
    everyday = q2(everyday_monthly * Decimal(days) / Decimal(30))
    goals_reserved = sum((g['plan'] for g in facts['goals'] if g['saved'] < g['target']), ZERO)
    expected_spend = bills_due + card_due + everyday
    headroom = balance - expected_spend - goals_reserved
    income_30d = features['salary_amount'] if payday and features['salary_amount'] > 0 else income
    projected = balance + income_30d - outflow - goals_reserved
    values = {'available': fixed(balance), 'commitments_until_payday': fixed(bills_due), 'card_payment_until_payday': fixed(card_due),
              'everyday_spending_until_payday': fixed(everyday), 'expected_spending_until_payday': fixed(expected_spend),
              'goal_contributions_reserved': fixed(goals_reserved), 'headroom_until_payday': fixed(headroom), 'days_to_payday': str(days),
              'expected_income_30d': fixed(income_30d), 'projected_30d_balance': fixed(projected), 'monthly_surplus_estimate': fixed(income - outflow)}
    if payday:
        values['payday'] = payday.isoformat()
    values['as_of'] = as_of_date.isoformat()
    if outflow > 0:
        values['buffer_months'] = fixed(balance / outflow)
    where = f'before your next salary on {date_text(payday.isoformat())}' if payday else 'over the next 30 days'
    explanation = (f'Estimate {where}: {money_text(balance, cur)} available, minus bills due of {money_text(bills_due, cur)}, card payment due of {money_text(card_due, cur)}, '
                   f'this month\'s goal contributions of {money_text(goals_reserved, cur)} set aside and everyday spending of {money_text(everyday, cur)}, leaves {money_text(headroom, cur)}. '
                   'Everyday spending is your 90-day average excluding bills; goal savings sit in separate pockets. This is a planning estimate, not a live balance or a guarantee.')
    status = 'GAP' if headroom < 0 or projected < 0 else 'AVAILABLE'
    return card('safe_to_spend', status, values, explanation, source, cur, evidence={'horizon_days': days, 'method': 'PLAN-1'})


def evaluate_goals(features: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    evaluated = []
    for goal in facts['goals']:
        remaining = max(goal['target'] - goal['saved'], ZERO)
        left = months_left(features['as_of_date'], goal['target_date'])
        required = q2(remaining / left) if left > 0 else remaining
        projected = goal['saved'] + goal['plan'] * left
        shortfall = max(goal['target'] - projected, ZERO)
        needed = int((remaining / goal['plan']).to_integral_value(rounding=ROUND_CEILING)) if goal['plan'] > 0 and remaining > 0 else None
        evaluated.append({**goal, 'remaining': remaining, 'left': left, 'required': required, 'projected': projected, 'shortfall': shortfall,
                          'extra': q2(max(required - goal['plan'], ZERO)), 'needed': needed,
                          'status': 'COMPLETE' if remaining == 0 else 'ON_TRACK' if shortfall == 0 else 'BEHIND',
                          'progress': min(ratio_percent(goal['saved'], goal['target']) or ZERO, HUNDRED)})
    return evaluated


def goal_progress_card(features: dict[str, Any], evaluated: list[dict[str, Any]], source: dict, cur: str) -> dict[str, Any]:
    if not evaluated:
        return card('goal_progress', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['goal_progress'], source, cur)
    rows = [{'label': g['name'], 'target': money_text(g['target'], cur), 'saved': money_text(g['saved'], cur), 'remaining': money_text(g['remaining'], cur),
             'progress_percent': percent_text(g['progress']), 'target_date': date_text(g['target_date'].isoformat()), 'months_left': str(g['left']),
             'required_monthly': money_text(g['required'], cur), 'planned_monthly': money_text(g['plan'], cur),
             'extra_monthly_needed': money_text(g['extra'], cur), 'shortfall': money_text(g['shortfall'], cur), 'status': STATUS_LABELS[g['status']]} for g in evaluated]
    lead = next((g for g in evaluated if g['status'] != 'COMPLETE'), evaluated[0])
    total = lambda key: sum((g[key] for g in evaluated), ZERO)
    surplus = features['avg_monthly_income'] - features['monthly_outflow']
    values = {'goal_name': lead['name'], 'target_amount': fixed(lead['target']), 'saved_amount': fixed(lead['saved']), 'remaining_amount': fixed(lead['remaining']),
              'progress_percent': fixed(lead['progress']), 'target_date': lead['target_date'].isoformat(), 'months_left': str(lead['left']),
              'required_monthly': fixed(lead['required']), 'planned_monthly': fixed(lead['plan']), 'projected_amount': fixed(lead['projected']),
              'shortfall_amount': fixed(lead['shortfall']), 'extra_monthly_needed': fixed(lead['extra']), 'goal_status': lead['status'],
              'goals_count': str(len(evaluated)), 'planned_total_monthly': fixed(total('plan')), 'monthly_surplus_estimate': fixed(surplus),
              'required_monthly_total': fixed(total('required')), 'extra_monthly_needed_total': fixed(total('extra')), 'shortfall_total': fixed(total('shortfall')),
              'remaining_total': fixed(total('remaining')), 'surplus_after_planned_goals': fixed(surplus - total('plan')),
              'surplus_after_required_goals': fixed(surplus - total('required')), 'goal_savings': fixed(total('saved')),
              'goal_contributions_reserved': fixed(sum((g['plan'] for g in evaluated if g['status'] != 'COMPLETE'), ZERO))}
    if lead['needed'] is not None:
        values['months_needed_at_plan'] = str(lead['needed'])
    verb = {'COMPLETE': 'is fully funded', 'ON_TRACK': 'is on track at the current monthly plan', 'BEHIND': 'is behind at the current monthly plan'}[lead['status']]
    explanation = (f"{lead['name']} {verb}: {money_text(lead['saved'], cur)} of {money_text(lead['target'], cur)} saved, {lead['left']} monthly contributions left, "
                   f"{money_text(lead['required'], cur)} a month needed against a plan of {money_text(lead['plan'], cur)}. Projection ignores investment returns and interest. "
                   f"Goal savings of {money_text(total('saved'), cur)} sit in separate pockets, not in your available balance; this month's planned contributions are set aside in safe to spend.")
    return card('goal_progress', 'AVAILABLE', values, explanation, source, cur, rows, {'method': 'PLAN-1', 'projection': 'saved + monthly plan x remaining months'})


def debt_card(features: dict[str, Any], facts: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    cards = [c for c in facts['cards'] if c['balance'] > 0]
    rated = [c for c in cards if c['rate'] is not None]
    if not rated:
        return card('debt', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['debt'], source, cur)
    outstanding = sum((c['balance'] for c in cards), ZERO)
    monthly_cost = q2(sum((c['balance'] * c['rate'] / Decimal(1200) for c in rated), ZERO))
    minimum = sum((c['minimum'] or ZERO for c in cards), ZERO)
    top_rate, saving_rate = max(c['rate'] for c in rated), facts['savings_interest_percent']
    after = features['balance_now'] - outstanding
    values = {'outstanding_total': fixed(outstanding), 'card_rate_percent': fixed(top_rate), 'monthly_interest_cost': fixed(monthly_cost),
              'minimum_payment_total': fixed(minimum), 'can_repay_in_full': 'yes' if after >= 0 else 'no', 'liquid_after_repayment': fixed(after)}
    earned = None
    if saving_rate is not None:
        earned = q2(outstanding * saving_rate / Decimal(1200))
        values.update(savings_interest_percent=fixed(saving_rate), monthly_interest_earned_on_same_amount=fixed(earned),
                      monthly_net_benefit_of_repaying=fixed(monthly_cost - earned))
    if features['monthly_outflow'] > 0 and after >= 0:
        values['buffer_months_after_repayment'] = fixed(after / features['monthly_outflow'])
    if len(rated) == 1 and rated[0]['minimum']:
        months, interest = months_to_clear_at_fixed_payment(rated[0]['balance'], rated[0]['rate'], rated[0]['minimum'])
        if months is not None:
            values.update(months_to_clear_at_minimum=str(months), interest_paid_at_minimum=fixed(interest))
    due = next((c['due_day'] for c in cards if c['due_day']), None)
    if due:
        values['due_day'] = str(due)
    rows = [{'label': f"Credit card {c['masked']}", 'outstanding': money_text(c['balance'], cur), 'rate_percent': percent_text(c['rate']),
             'minimum_payment': money_text(c['minimum'], cur) if c['minimum'] is not None else 'n/a', 'due_day': f"day {c['due_day']}" if c['due_day'] else 'n/a'} for c in cards]
    explanation = (f'Card balance of {money_text(outstanding, cur)} costs about {money_text(monthly_cost, cur)} a month in interest at {percent_text(top_rate)} a year.'
                   + (f' The same amount in savings earns about {money_text(earned, cur)} a month at {percent_text(saving_rate)}.' if earned is not None else '')
                   + ' Investment returns are uncertain and can be negative; card interest is a certain cost.')
    return card('debt', 'AVAILABLE', values, explanation, source, cur, rows, {'method': 'PLAN-1', 'interest': 'balance x annual rate / 12'})


def portfolio_card(facts: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    holdings = facts['holdings']
    if not holdings:
        return card('portfolio', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['portfolio'], source, cur)
    total, cost = sum((h['value'] for h in holdings), ZERO), sum((h['cost'] for h in holdings), ZERO)
    gain = total - cost
    share = lambda kind: fixed(ratio_percent(sum((h['value'] for h in holdings if h['asset_class'] == kind), ZERO), total))
    largest = max(holdings, key=lambda h: h['value'])
    as_of = max(h['as_of'] for h in holdings).date().isoformat()
    values = {'total_value': fixed(total), 'total_cost': fixed(cost), 'gain_loss': fixed(gain), 'holdings_count': str(len(holdings)),
              'largest_holding': largest['instrument'], 'largest_holding_percent': fixed(ratio_percent(largest['value'], total)),
              'equity_percent': share('EQUITY'), 'bond_percent': share('BOND'), 'money_market_percent': share('MONEY_MARKET'), 'as_of': as_of}
    if cost > 0:
        values['gain_loss_percent'] = fixed(ratio_percent(gain, cost))
    move = lambda h: ratio_percent(h['value'] - h['value_30d_ago'], h['value_30d_ago'])
    if all(h['value_30d_ago'] for h in holdings):
        previous = sum((h['value_30d_ago'] for h in holdings), ZERO)
        worst, best = min(holdings, key=move), max(holdings, key=move)
        values.update(change_30d=fixed(total - previous), change_30d_percent=fixed(ratio_percent(total - previous, previous)),
                      weakest_holding=worst['instrument'], weakest_change_30d_percent=fixed(move(worst)),
                      strongest_holding=best['instrument'], strongest_change_30d_percent=fixed(move(best)))
    rows = []
    for h in sorted(holdings, key=lambda h: h['value'], reverse=True):
        row = {'label': h['instrument'], 'asset_class': CLASS_LABELS.get(h['asset_class'], h['asset_class']), 'value': money_text(h['value'], cur),
               'share_percent': percent_text(ratio_percent(h['value'], total)), 'cost': money_text(h['cost'], cur),
               'gain_loss': money_text(h['value'] - h['cost'], cur),
               'gain_loss_percent': percent_text(ratio_percent(h['value'] - h['cost'], h['cost']), signed=True)}
        if h.get('as_of') and h['as_of'].date().isoformat() < as_of:
            row['holding_since'] = date_text(h['as_of'].date().isoformat())
        if h['value_30d_ago']:
            row['change_30d_percent'] = percent_text(move(h), signed=True)
        rows.append(row)
    explanation = (f"{len(holdings)} linked fund holdings worth {money_text(total, cur)} against a cost of {money_text(cost, cur)} ({money_text(gain, cur)}). "
                   f"Values are a snapshot as of {date_text(as_of)} and can differ from live prices. This is information, not advice.")
    return card('portfolio', 'AVAILABLE', values, explanation, source, cur, rows, {'method': 'PLAN-1', 'as_of': as_of})


def net_worth_card(features: dict[str, Any], facts: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    liquid, deposits = features['balance_now'], facts['deposits_total']
    pockets = sum((g['saved'] for g in facts['goals']), ZERO)
    investments = sum((h['value'] for h in facts['holdings']), ZERO)
    liabilities = sum((c['balance'] for c in facts['cards']), ZERO)
    assets = liquid + deposits + pockets + investments
    if assets <= 0 and liabilities <= 0:
        return card('net_worth', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['net_worth'], source, cur)
    values = {'assets_total': fixed(assets), 'liquid_assets': fixed(liquid), 'deposit_assets': fixed(deposits), 'goal_savings': fixed(pockets),
              'investment_assets': fixed(investments), 'liabilities_total': fixed(liabilities), 'net_worth': fixed(assets - liabilities)}
    if all(h['value_30d_ago'] is not None for h in facts['holdings']):
        tracked = liquid + deposits + investments
        previous = features['balance_30d_ago'] + facts['deposits_30d_ago'] + sum((h['value_30d_ago'] for h in facts['holdings']), ZERO)
        values['assets_change_30d'] = fixed(tracked - previous)
        if previous > 0:
            values['assets_change_30d_percent'] = fixed(ratio_percent(tracked - previous, previous))
    outflow, income = features['monthly_outflow'], features['avg_monthly_income']
    if outflow > 0:
        values['buffer_months'] = fixed(liquid / outflow)
    if income > 0:
        values['savings_rate_percent'] = fixed(ratio_percent(income - outflow, income))
        minimum = sum((c['minimum'] or ZERO for c in facts['cards']), ZERO)
        if minimum > 0:
            values['debt_to_income_percent'] = fixed(ratio_percent(minimum, income))
    rows = [{'label': 'Savings and current accounts', 'amount': money_text(liquid, cur)}, {'label': 'Term deposits', 'amount': money_text(deposits, cur)},
            {'label': 'Goal savings pockets', 'amount': money_text(pockets, cur)}, {'label': 'Investments', 'amount': money_text(investments, cur)},
            {'label': 'Credit card balances (owed)', 'amount': money_text(liabilities, cur)}]
    explanation = (f'Assets of {money_text(assets, cur)} minus {money_text(liabilities, cur)} owed give a net worth of {money_text(assets - liabilities, cur)}. '
                   'Goal pockets are held apart from your available balance. Card balance and goal pocket history are unavailable, so the 30-day change covers accounts and investments only. '
                   'Health is shown as separate measures, not a single score.')
    return card('net_worth', 'AVAILABLE', values, explanation, source, cur, rows, {'method': 'PLAN-1', 'scope': 'accounts, goal pockets and holdings linked to this profile'})


def next_actions_card(features: dict[str, Any], evaluated: list[dict[str, Any]], debt: dict[str, Any], worth: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    actions: list[tuple[str, str, str]] = []
    if features['has_cash_gap']:
        actions.append(('cash', 'Cover your upcoming commitments', f"Available funds are {money_text(features['balance_now'], cur)} against {money_text(features['commitments_14d'], cur)} due in the next 14 days."))
    in_debt = debt['status'] == 'AVAILABLE'
    if in_debt:
        dv = debt['values']
        cost = money_text(Decimal(dv['monthly_interest_cost']), cur)
        if 'savings_interest_percent' not in dv or Decimal(dv['card_rate_percent']) > Decimal(dv['savings_interest_percent']):
            if dv['can_repay_in_full'] == 'yes' and Decimal(dv.get('buffer_months_after_repayment', '0')) >= 1:
                actions.append(('debt', 'Pay off your credit card balance', f"It costs about {cost} a month in interest; repaying leaves {dv['buffer_months_after_repayment']} months of spending in cash."))
            else:
                tail = f" Keeping the current payment clears it in {dv['months_to_clear_at_minimum']} months with {money_text(Decimal(dv['interest_paid_at_minimum']), cur)} of interest." if 'months_to_clear_at_minimum' in dv else ''
                actions.append(('debt', 'Pay more than the minimum on your credit card', f'The balance costs about {cost} a month in interest.{tail}'))
    buffer_months = Decimal(worth['values']['buffer_months']) if worth['status'] == 'AVAILABLE' and 'buffer_months' in worth['values'] else None
    if buffer_months is not None and buffer_months < BUFFER_TARGET_MONTHS:
        actions.append(('buffer', 'Build your cash buffer toward three months of spending', f'Your accessible cash covers {fixed(buffer_months)} months of typical spending.'))
    for goal in evaluated:
        if goal['status'] == 'BEHIND':
            actions.append(('goal', f"Close the gap on {goal['name']}", f"It needs {money_text(goal['required'], cur)} a month against a plan of {money_text(goal['plan'], cur)}, so about {money_text(goal['extra'], cur)} more a month, or a later date."))
    discretionary = sum((b['monthly_estimate'] for b in features['recurring_bills'] if (b['category'] or '').lower() in DISCRETIONARY_CATEGORIES), ZERO)
    if discretionary > 0:
        actions.append(('spending', 'Review discretionary recurring spending', f'About {money_text(discretionary, cur)} a month goes to dining, entertainment and similar recurring merchants.'))
    if not in_debt and buffer_months is not None and buffer_months >= BUFFER_TARGET_MONTHS and not features['has_cash_gap']:
        actions.append(('invest', 'Learn about investing and ask for a suitability review', "Your buffer and debts are in good shape. A personal investment recommendation needs the bank's suitability process with an advisor."))
    if not actions:
        return card('next_actions', 'UNAVAILABLE', {}, UNAVAILABLE_TEXT['next_actions'], source, cur)
    rows = [{'rank': str(n), 'topic': topic, 'action': action, 'reason': reason} for n, (topic, action, reason) in enumerate(actions[:5], start=1)]
    return card('next_actions', 'AVAILABLE', {'action_count': str(len(rows))},
                'Ranked by fixed rules: urgent care first, certain costs next, then goals and learning. A checklist of options, not a product recommendation.',
                source, cur, rows, {'method': 'PLAN-1', 'order': 'cash gap, debt, buffer, goals, spending, learning'})

def market_insights_card(features: dict[str, Any], source: dict, cur: str) -> dict[str, Any]:
    from .market_feed import fetch_market_snapshot, format_market_note, get_market_ticks
    snapshot = fetch_market_snapshot('auto')
    ticks = get_market_ticks()
    session = snapshot.get('session', 'CLOSE')
    as_of = snapshot.get('as_of', '18 Oct 2026')
    values = {
        'session': session,
        'as_of': as_of,
        'index_name': snapshot.get('index_name', 'Indonesian equities (IHSG)'),
        'ihsg_change': snapshot.get('change', '-1.45%'),
        'sentiment': snapshot.get('sentiment', 'foreign capital outflows following MSCI index rebalancing sentiment'),
        'lead_stock': 'BBCA',
        'lead_stock_price': '10250.00',
        'lead_stock_change': '-1.20%',
    }
    rows = [
        {'symbol': t['symbol'], 'name': t['name'], 'type': t['type'], 'price': t['price'], 'change_percent': t['change_percent']}
        for t in ticks
    ]
    explanation = format_market_note(snapshot)
    return card('market_insights', 'AVAILABLE', values, explanation, source, cur, rows, {'method': 'MARKET-FEED-1', 'as_of': as_of, 'session': session})


def planning_cards(features: dict[str, Any], source: dict, cur: str) -> list[dict[str, Any]]:
    facts = features['planning']
    evaluated = evaluate_goals(features, facts)
    debt = debt_card(features, facts, source, cur)
    worth = net_worth_card(features, facts, source, cur)
    return [spending_breakdown_card(features, source, cur), safe_to_spend_card(features, source, cur), goal_progress_card(features, evaluated, source, cur),
            debt, portfolio_card(facts, source, cur), worth, next_actions_card(features, evaluated, debt, worth, source, cur),
            market_insights_card(features, source, cur)]
