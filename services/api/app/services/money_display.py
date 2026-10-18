"""Customer-facing text for validated Decimal strings. Display only; the Decimal strings stay authoritative."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

MONEY_KEYS = frozenset({
    'available', 'commitments', 'difference', 'previous_spend', 'current_spend', 'change', 'amount',
    'salary_amount', 'average_monthly', 'idle_cash', 'savings_balance', 'monthly_outflow', 'balance',
    'balance_now', 'balance_30d_avg', 'balance_30d_min',
    'total_spend', 'income_monthly', 'top_category_amount', 'biggest_increase_amount',
    'commitments_until_payday', 'expected_spending_until_payday', 'headroom_until_payday', 'expected_income_30d',
    'projected_30d_balance', 'monthly_surplus_estimate',
    'target_amount', 'saved_amount', 'remaining_amount', 'required_monthly', 'planned_monthly', 'projected_amount',
    'shortfall_amount', 'extra_monthly_needed', 'planned_total_monthly',
    'required_monthly_total', 'extra_monthly_needed_total', 'shortfall_total', 'remaining_total', 'surplus_after_planned_goals', 'surplus_after_required_goals',
    'outstanding_total', 'monthly_interest_cost', 'minimum_payment_total', 'monthly_interest_earned_on_same_amount',
    'monthly_net_benefit_of_repaying', 'liquid_after_repayment', 'interest_paid_at_minimum',
    'total_value', 'total_cost', 'gain_loss', 'change_30d',
    'assets_total', 'liquid_assets', 'deposit_assets', 'investment_assets', 'liabilities_total', 'net_worth', 'assets_change_30d',
    'discretionary_total', 'essential_total', 'variable_total', 'monthly_total', 'bills_monthly_total', 'regular_monthly_total',
    'everyday_spending_until_payday', 'goal_contributions_reserved', 'card_payment_until_payday', 'goal_savings',
})
DATE_KEYS = frozenset({'maturity_date', 'target_date', 'payday', 'as_of'})


def money_text(value: Any, currency: Optional[str] = None) -> str:
    """IDR 1,150,000 / IDR 261,666.67: thousands separators, cents only when non-zero."""
    text = f"{Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    if text.endswith('.00'):
        text = text[:-3]
    return f'{currency} {text}' if currency else text


def date_text(value: str) -> str:
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return f'{d.day} {d:%b %Y}'


def is_percent_key(key: str) -> bool:
    return key.endswith('_percent')


def display_values(insight: dict[str, Any]) -> dict[str, str]:
    currency = insight.get('currency')
    shown: dict[str, str] = {}
    for key, value in (insight.get('values') or {}).items():
        if value is None:
            continue
        if key in MONEY_KEYS:
            shown[key] = money_text(value, currency)
        elif is_percent_key(key):
            shown[key] = f'{value}%'
        elif key in DATE_KEYS:
            shown[key] = date_text(str(value))
        else:
            shown[key] = str(value)
    return shown
