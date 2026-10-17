"""Deterministic answers to money-planning and investment-context questions for the SIMULATED engine.

Every figure comes from the validated insight cards; nothing here calculates or invents a number. Live Gemini answers
the same questions from the same cards, so this module also documents the expected shape of a good answer.
"""
import re
from typing import Optional

from ..money_display import display_values

DEBT_WORDS = ('pay down', 'pay off', 'paying off', 'paying down', 'debt', 'credit card', 'repay', 'extra cash', 'save or invest', 'owe')
DROP_WORDS = ('drop', 'dropped', 'fell', 'falling', 'decline', 'losing', 'lost money', 'is this normal', 'should i sell', 'sell')
PORTFOLIO_WORDS = ('portfolio', 'performing', 'performance', 'returns', 'holdings', 'my investments')
GOAL_WORDS = ('on track', 'my goal', 'goals', 'how far', 'progress')
SAFE_WORDS = ('safely spend', 'safe to spend', 'how much can i spend', 'how much can i save', 'shortfall', 'payday', 'run short', 'enough money', 'month end', 'end of the month')
SPENDING_WORDS = ('where is my money', 'money going', 'overspend', 'spending too much', 'spend less', 'cut spending', 'reduce spending', 'stop spending')
RECURRING_WORDS = ('subscription', 'recurring', 'cancel', 'monthly payments', 'cut costs', 'cut my bills')
HEALTH_WORDS = ('net worth', 'financial health', 'how am i doing', 'financial position')
NEXT_WORDS = ('next step', 'what should i do next', 'what product', 'improve my finances', 'where should i start')
ADVICE_NOTE = "Personal investment recommendations are not enabled here, so I can't tell you what to buy, sell or hold. A personal recommendation needs the bank's suitability review with an advisor, which looks at your goal, time horizon and risk profile."
OFFER = 'Would you like your relationship manager to review this with you through the bank\'s official channels?'


def planning_intent(message: str, route: str) -> Optional[str]:
    s = message.casefold()
    if route == 'WEALTH':
        if any(w in s for w in DEBT_WORDS):
            return 'debt'
        if any(w in s for w in DROP_WORDS):
            return 'market_drop'
        if any(w in s for w in PORTFOLIO_WORDS):
            return 'portfolio'
        if any(w in s for w in GOAL_WORDS):
            return 'goals'
        return 'invest_start'
    if route == 'SAVINGS':
        for intent, words in (('debt', DEBT_WORDS), ('recurring', RECURRING_WORDS), ('health', HEALTH_WORDS), ('next', NEXT_WORDS), ('goals', GOAL_WORDS), ('safe', SAFE_WORDS), ('spending', SPENDING_WORDS)):
            if any(w in s for w in words):
                return intent
    return None


def card(financial: list, key: str) -> Optional[dict]:
    return next((c for c in financial if c['key'] == key and c['status'] != 'UNAVAILABLE'), None)


def note_sentence(kb: dict) -> str:
    content = (kb.get('market_moves') or {}).get('content', '')
    match = re.search(r'(?:Synthetic )?[Mm]arket note[^:]*:[^.]*\.[^.]*\.', content)
    return match.group(0) if match else ''


def build(intent: str, financial: list, kb: dict) -> Optional[tuple[str, list[str]]]:
    """Return (text, knowledge keys used) or None when the needed insight is unavailable."""
    if intent == 'spending' and (c := card(financial, 'spending_breakdown')):
        v = display_values(c)
        lines = [f"- {r['label']}: {r['amount']} ({r['share_percent']})" for r in c['rows'][:3]]
        rise = f" {v['biggest_increase_category']} rose the most, up {v['biggest_increase_percent']} ({v['biggest_increase_amount']})." if 'biggest_increase_category' in v else ''
        share = f", about {v['spend_to_income_percent']} of your typical monthly income" if 'spend_to_income_percent' in v else ''
        tail = f"{rise} A practical first step is to set a ceiling for the category that is growing fastest and check what changed. This is a snapshot, not a live balance.".strip()
        return (f"Over the last 30 days you spent {v['total_spend']}{share}. The biggest categories:\n" + '\n'.join(lines) + '\n\n' + tail, ['spending_control'])
    if intent == 'safe' and (c := card(financial, 'safe_to_spend')):
        v = display_values(c)
        until = f"before your next salary on {v['payday']}" if 'payday' in v else 'over the next 30 days'
        return (f"{until[0].upper() + until[1:]} you can expect about {v['headroom_until_payday']} left: {v['available']} available minus typical spending of {v['expected_spending_until_payday']}. "
                f"Over the next 30 days the projection is {v['projected_30d_balance']}, and your typical monthly surplus is {v['monthly_surplus_estimate']}.\n\n"
                f"Your cash covers {v.get('buffer_months', 'n/a')} months of typical spending. This is an estimate from your last 90 days, not a live balance or a guarantee.", ['safe_to_spend'])
    if intent == 'goals' and (c := card(financial, 'goal_progress')):
        v = display_values(c)
        lines = [f"- {r['label']}: {r['saved']} of {r['target']} ({r['progress_percent']}) by {r['target_date']}. It needs {r['required_monthly']} a month against a plan of {r['planned_monthly']}: {r['status'].lower()}." for r in c['rows']]
        close = ''
        if v['goal_status'] == 'BEHIND':
            close = f"\n\nTo close the gap on {v['goal_name']} you could add about {v['extra_monthly_needed']} a month, or move the date: at the current plan it takes about {v.get('months_needed_at_plan', 'more')} months."
        return ('Here is where your goals stand:\n' + '\n'.join(lines) + close + '\n\nProjections ignore interest and investment returns.', ['goal_planning'])
    if intent == 'debt' and (c := card(financial, 'debt')):
        v = display_values(c)
        slow = f" Keeping only the current minimum would take {v['months_to_clear_at_minimum']} months and {v['interest_paid_at_minimum']} in interest." if 'months_to_clear_at_minimum' in v else ''
        keep = f" Repaying in full would leave {v['liquid_after_repayment']} in your accounts, about {v['buffer_months_after_repayment']} months of spending." if 'buffer_months_after_repayment' in v else ''
        earn = f" The same amount in savings earns about {v['monthly_interest_earned_on_same_amount']} a month at {v['savings_interest_percent']}." if 'monthly_interest_earned_on_same_amount' in v else ''
        return (f"Your card balance of {v['outstanding_total']} costs about {v['monthly_interest_cost']} a month in interest at {v['card_rate_percent']} a year.{earn}{keep}{slow}\n\n"
                "Card interest is a certain cost, while investment returns are uncertain and can be negative. A common order is: keep essentials and a cash buffer, clear high-interest debt, fund near-term goals, then consider investing. "
                + ADVICE_NOTE, ['debt_vs_save_invest', 'suitability_process'])
    if intent == 'recurring' and (c := card(financial, 'recurring')):
        v = display_values(c)
        rows = [r for r in c['rows'] if r.get('type') == 'Discretionary'] or c['rows'][:3]
        lines = [f"- {r['label']} ({r['category']}): about {r['monthly_estimate']} a month" for r in rows[:4]]
        return (f"Your recurring payments add up to {v['amount']} across {v['merchant_count']} merchants. The ones you control most are:\n" + '\n'.join(lines)
                + "\n\nI can't cancel or change anything; do that with the merchant or in the bank's menus.", ['spending_control'])
    if intent == 'health' and (c := card(financial, 'net_worth')):
        v = display_values(c)
        move = f" Your assets changed {v['assets_change_30d']} ({v['assets_change_30d_percent']}) over 30 days." if 'assets_change_30d' in v else ''
        return (f"Your net worth is {v['net_worth']}: {v['assets_total']} of assets minus {v['liabilities_total']} owed.{move}\n\n"
                f"Your cash buffer covers {v.get('buffer_months', 'n/a')} months of spending, you keep {v.get('savings_rate_percent', 'n/a')} of income, and minimum card payments take {v.get('debt_to_income_percent', 'n/a')} of income. "
                'These are separate measures, not a score, and cover only the accounts and holdings linked to your profile.', ['financial_health'])
    if intent == 'next' and (c := card(financial, 'next_actions')):
        lines = [f"{r['rank']}. {r['action']}: {r['reason']}" for r in c['rows'][:3]]
        return ('Here are the next steps worth considering, in order:\n' + '\n'.join(lines) + '\n\nThese are options, not product recommendations.', ['financial_health', 'debt_vs_save_invest'])
    if intent in {'portfolio', 'market_drop'} and (c := card(financial, 'portfolio')):
        v = display_values(c)
        moved = f" Over 30 days the total moved {v['change_30d']} ({v['change_30d_percent']})." if 'change_30d' in v else ''
        mix = f"Allocation: {v['equity_percent']} equity, {v['bond_percent']} bonds, {v['money_market_percent']} money market."
        if intent == 'market_drop' and 'weakest_holding' in v:
            return (f"{v['weakest_holding']} is down {v['weakest_change_30d_percent'].lstrip('-')} over 30 days, which explains most of the move in your {v['total_value']} portfolio.{moved} "
                    f"Equity funds rise and fall, and a decline of several percent in a month is common. {note_sentence(kb)} {ADVICE_NOTE} {OFFER}".replace('  ', ' '), ['market_moves', 'suitability_process'])
        return (f"Your {v['holdings_count']} fund holdings are worth {v['total_value']} against a cost of {v['total_cost']}: {v['gain_loss']} ({v.get('gain_loss_percent', 'n/a')}).{moved} {mix}\n\n"
                f"This is a snapshot, not advice. {ADVICE_NOTE}", ['portfolio_reading', 'suitability_process'])
    if intent == 'invest_start':
        v = display_values(card(financial, 'safe_to_spend') or {})
        worth = display_values(card(financial, 'net_worth') or {})
        debt = display_values(card(financial, 'debt') or {})
        facts = []
        if 'buffer_months' in worth:
            facts.append(f"your cash covers {worth['buffer_months']} months of spending")
        if 'outstanding_total' in debt:
            facts.append(f"you owe {debt['outstanding_total']} on a card at {debt['card_rate_percent']}")
        if 'monthly_surplus_estimate' in v:
            facts.append(f"your typical monthly surplus is {v['monthly_surplus_estimate']}")
        base = ('Before investing it helps to check three things: ' + ('; '.join(facts) + '. ' if facts else 'your cash buffer, any high-interest debt and the goal for the money. '))
        return (base + 'Funds pool money into a basket of holdings: money market funds usually move little, bond funds move with interest rates, and equity or index funds can fall as well as rise. Small regular amounts let you start with limited money, but returns are never guaranteed. '
                + ADVICE_NOTE, ['investing_basics', 'suitability_process'])
    return None


ORIGINAL_CARDS = frozenset({'cash_flow', 'spending', 'recurring', 'salary', 'idle_cash', 'term_deposit', 'balance_trend'})
BASE_CARDS = frozenset({'cash_flow', 'spending', 'balance_trend', 'salary'})
PLANNING_CARDS = frozenset({'spending_breakdown', 'safe_to_spend', 'goal_progress', 'debt', 'portfolio', 'net_worth', 'next_actions'})
INTENT_CARDS = {
    'spending': {'spending_breakdown', 'recurring'},
    'safe': {'safe_to_spend', 'goal_progress'},
    'goals': {'goal_progress', 'safe_to_spend'},
    'debt': {'debt', 'safe_to_spend', 'net_worth', 'goal_progress', 'portfolio'},
    'recurring': {'recurring', 'spending_breakdown'},
    'health': {'net_worth', 'debt', 'portfolio', 'goal_progress', 'safe_to_spend'},
    'next': PLANNING_CARDS,
    'portfolio': {'portfolio', 'goal_progress', 'safe_to_spend', 'net_worth'},
    'market_drop': {'portfolio', 'goal_progress', 'safe_to_spend'},
    'invest_start': {'safe_to_spend', 'debt', 'portfolio', 'goal_progress', 'net_worth'},
}


def select_context(financial: list, message: str, route: str) -> list:
    """Data minimization: only the insight cards that serve this question are read for the answer."""
    intent = planning_intent(message, route)
    allowed = ORIGINAL_CARDS if not intent else BASE_CARDS | INTENT_CARDS[intent]
    return [c for c in financial if c['key'] in allowed]
