"""Planning calculators: figures are deterministic, signed correctly, honest about missing data and covered by the source hash."""
from datetime import date, datetime
from decimal import Decimal
from app.core.database import SessionLocal
from app.models.banking import BankAccount, BankCustomer, BankGoal, BankHolding
from app.models.relationships import Party, Source
from app.services.insights_pipeline import insight_cards
from app.services.money_display import display_values
from app.services.planning import months_left, months_to_clear_at_fixed_payment, next_payday


def cards(db, name='Dina Rahma'):
    party = db.query(Party).filter_by(name=name, tenant_id='demo-bank').one()
    return {c['key']: c for c in insight_cards(db, party)}


def dina_accounts(db, product):
    customer = db.query(BankCustomer).filter_by(full_name='Dina Rahma').one()
    return db.query(BankAccount).filter_by(customer_id=customer.id, product=product).all()


def test_goal_progress_matches_hand_calculation_for_each_goal():
    with SessionLocal() as db:
        goal = cards(db)['goal_progress']
    v = goal['values']
    assert (v['goal_name'], v['goal_status']) == ('Dana Pendidikan Anak', 'BEHIND')
    assert (v['remaining_amount'], v['months_left'], v['required_monthly']) == ('15000000.00', '8', '1875000.00')
    assert (v['projected_amount'], v['shortfall_amount'], v['extra_monthly_needed'], v['months_needed_at_plan']) == ('17000000.00', '3000000.00', '375000.00', '10')
    assert [r['status'] for r in goal['rows']] == ['Behind', 'Behind'] and goal['rows'][1]['required_monthly'] == 'IDR 857,142.86'


def test_goal_totals_and_per_goal_extras_are_calculated_for_the_model_to_quote():
    with SessionLocal() as db:
        goal = cards(db)['goal_progress']
    v, emergency = goal['values'], goal['rows'][1]
    assert (emergency['remaining'], emergency['months_left'], emergency['extra_monthly_needed']) == ('IDR 12,000,000', '14', 'IDR 357,142.86')
    assert (v['required_monthly_total'], v['extra_monthly_needed_total']) == ('2732142.86', '732142.86')
    assert (v['shortfall_total'], v['remaining_total']) == ('8000000.00', '27000000.00')
    assert (v['surplus_after_planned_goals'], v['surplus_after_required_goals']) == ('931666.67', '199523.81')
    assert display_values(goal)['required_monthly_total'] == 'IDR 2,732,142.86'


def test_balance_series_is_the_daily_path_behind_the_balance_card_and_stays_out_of_the_prompt():
    from decimal import ROUND_HALF_UP
    from app.services.assistant.engine import readable_insight
    with SessionLocal() as db:
        trend = cards(db)['balance_trend']
    series, v = trend['series'], trend['values']
    days = [date.fromisoformat(point['date']) for point in series]
    balances = [Decimal(point['balance']) for point in series]
    assert len(series) == 30 and all((later - earlier).days == 1 for earlier, later in zip(days, days[1:]))
    assert balances[-1] == Decimal(v['balance_now']) and min(balances) == Decimal(v['balance_30d_min'])
    assert (sum(balances) / 30).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) == Decimal(v['balance_30d_avg'])
    assert 'series' not in readable_insight(trend)


def test_goal_headroom_keeps_its_sign_when_the_goals_outgrow_the_surplus():
    with SessionLocal() as db:
        db.query(BankGoal).filter_by(name='Dana Darurat').update({'target_amount': Decimal('60000000.00')})
        db.commit()
        v = cards(db)['goal_progress']['values']
    assert v['required_monthly_total'] == '5946428.57'
    assert v['surplus_after_planned_goals'] == '931666.67' and v['surplus_after_required_goals'] == '-3014761.90'


def test_recurring_subtotals_add_up_to_the_monthly_estimates_in_the_rows():
    with SessionLocal() as db:
        recurring = cards(db)['recurring']
    v = recurring['values']
    assert (v['essential_total'], v['variable_total'], v['discretionary_total']) == ('2380000.00', '2483333.33', '705000.00')
    assert Decimal(v['monthly_total']) == sum(Decimal(v[k]) for k in ('essential_total', 'variable_total', 'discretionary_total')) == Decimal('5568333.33')
    assert Decimal(v['monthly_total']) == Decimal(v['committed_monthly_total']) + Decimal(v['regular_monthly_total'])
    transport = [r for r in recurring['rows'] if r['category'] == 'Transport']
    assert len(transport) == 3 and {r['category_monthly_total'] for r in transport} == {'IDR 683,333.33'}


def test_subscriptions_are_cancellable_bills_are_obligations_and_weekly_shopping_is_a_regular_pattern():
    with SessionLocal() as db:
        built = cards(db)
    recurring, safe = built['recurring'], built['safe_to_spend']
    rows = {r['label']: r for r in recurring['rows']}
    groups = lambda name: {label for label, r in rows.items() if r['group'] == name}
    assert groups('Bill') == {'SMP Islam Al-Azhar Bekasi', 'IndiHome Telkom', 'PLN Persero', 'BPJS Kesehatan'}
    assert groups('Subscription') == {'Spotify AB'} and rows['Spotify AB']['cancellable'] == 'true'
    assert all(rows[label]['cancellable'] == 'false' for label in groups('Bill') | groups('Regular spending'))
    v = recurring['values']
    assert (v['bills_count'], v['bills_monthly_total'], v['subscriptions_count']) == ('4', '2380000.00', '1')
    assert Decimal(v['committed_monthly_total']) == Decimal(v['bills_monthly_total']) + Decimal(v['subscriptions_monthly_total']) == Decimal('2425000.00')
    assert Decimal(v['monthly_total']) == Decimal(v['committed_monthly_total']) + Decimal(v['regular_monthly_total'])
    assert safe['values']['headroom_until_payday'] == '9452222.22' and safe['values']['everyday_spending_until_payday'] == '1047777.78'
    for weekly in ('Super Indo Bekasi', 'Restoran Padang Sederhana'):
        assert rows[weekly]['group'] == 'Regular spending' and rows[weekly]['cadence'] == 'Weekly'
        assert date(2026, 10, 15) <= datetime.strptime(rows[weekly]['next_expected'], '%d %b %Y').date() <= date(2026, 10, 22)


def test_safe_to_spend_is_available_minus_each_listed_use_and_reserves_goal_contributions():
    with SessionLocal() as db:
        v = cards(db)['safe_to_spend']['values']
    uses = ('commitments_until_payday', 'card_payment_until_payday', 'everyday_spending_until_payday')
    assert Decimal(v['expected_spending_until_payday']) == sum(Decimal(v[k]) for k in uses)
    assert Decimal(v['headroom_until_payday']) == Decimal(v['available']) - Decimal(v['expected_spending_until_payday']) - Decimal(v['goal_contributions_reserved'])
    assert (v['goal_contributions_reserved'], v['everyday_spending_until_payday'], v['headroom_until_payday']) == ('2000000.00', '1047777.78', '9452222.22')
    assert v['projected_30d_balance'] == '13431666.67'


def test_card_minimum_due_before_payday_is_part_of_expected_spending():
    with SessionLocal() as db:
        for account in dina_accounts(db, 'CREDIT_CARD'):
            account.payment_due_day = 20
        db.commit()
        v = cards(db)['safe_to_spend']['values']
    assert v['card_payment_until_payday'] == '210000.00' and v['headroom_until_payday'] == '9242222.22'


def test_goal_is_on_track_once_the_plan_covers_the_requirement():
    with SessionLocal() as db:
        db.query(BankGoal).filter_by(name='Dana Pendidikan Anak').update({'monthly_plan': Decimal('2000000.00')})
        db.commit()
        goal = cards(db)['goal_progress']
    assert goal['values']['goal_status'] == 'ON_TRACK' and goal['values']['shortfall_amount'] == '0.00'
    assert goal['rows'][0]['status'] == 'On track'


def test_card_interest_is_certain_cost_and_minimum_payment_trap_is_quantified():
    with SessionLocal() as db:
        debt = cards(db)['debt']
    v = debt['values']
    assert (v['monthly_interest_cost'], v['monthly_interest_earned_on_same_amount'], v['monthly_net_benefit_of_repaying']) == ('84000.00', '8750.00', '75250.00')
    assert (v['months_to_clear_at_minimum'], v['interest_paid_at_minimum']) == ('26', '1217465.88')
    assert (v['can_repay_in_full'], v['liquid_after_repayment'], v['buffer_months_after_repayment']) == ('yes', '8300000.00', '1.49')
    assert months_to_clear_at_fixed_payment(Decimal('1000000'), Decimal('24'), Decimal('10000')) == (None, None)


def test_portfolio_keeps_the_sign_of_losses_and_allocation_adds_up():
    with SessionLocal() as db:
        portfolio = cards(db)['portfolio']
    v = portfolio['values']
    assert (v['total_value'], v['gain_loss'], v['gain_loss_percent'], v['change_30d_percent']) == ('15524000.00', '24000.00', '0.15', '-1.74')
    assert (v['weakest_holding'], v['weakest_change_30d_percent']) == ('Reksa Dana Indeks IDX30', '-6.10')
    assert abs(sum(Decimal(v[k]) for k in ('equity_percent', 'bond_percent', 'money_market_percent')) - 100) <= Decimal('0.02')
    shown = display_values(portfolio)
    assert shown['gain_loss_percent'] == '0.15%' and shown['total_value'] == 'IDR 15,524,000' and shown['as_of'] == '17 Oct 2026'
    assert next(r for r in portfolio['rows'] if r['label'] == 'Reksa Dana Indeks IDX30')['gain_loss'] == 'IDR -175,000'
    assert next(r for r in portfolio['rows'] if 'BBCA' in r['label'])['holding_since'] == '15 Jun 2026'
    assert 'holding_since' not in next(r for r in portfolio['rows'] if r['label'] == 'Reksa Dana Indeks IDX30')


def test_net_worth_counts_goal_pockets_subtracts_liabilities_and_omits_unknown_history():
    with SessionLocal() as db:
        worth = cards(db)['net_worth']['values']
        assert (worth['assets_total'], worth['goal_savings'], worth['liabilities_total'], worth['net_worth']) == ('36024000.00', '8000000.00', '4200000.00', '31824000.00')
        assert worth['assets_change_30d'] == '2190000.00'
        db.query(BankHolding).filter_by(instrument='Reksa Dana Indeks IDX30').update({'value_30d_ago': None})
        db.commit()
        assert 'assets_change_30d' not in cards(db)['net_worth']['values']


def test_safe_to_spend_reports_a_shortfall_instead_of_hiding_it():
    with SessionLocal() as db:
        healthy = cards(db)['safe_to_spend']
        assert healthy['status'] == 'AVAILABLE' and healthy['values']['payday'] == '2026-10-25'
        for account in dina_accounts(db, 'SAVINGS'):
            account.balance = Decimal('100000.00')
        db.commit()
        short = cards(db)['safe_to_spend']
    assert short['status'] == 'GAP' and Decimal(short['values']['headroom_until_payday']) < 0


def test_investing_step_appears_only_when_debt_free_with_a_three_month_buffer():
    with SessionLocal() as db:
        topics = [r['topic'] for r in cards(db)['next_actions']['rows']]
        assert topics[:2] == ['debt', 'buffer'] and 'invest' not in topics
        for account in dina_accounts(db, 'CREDIT_CARD'):
            account.balance = Decimal('0.00')
        for account in dina_accounts(db, 'SAVINGS'):
            account.balance = Decimal('30000000.00')
        db.commit()
        rows = cards(db)['next_actions']['rows']
    assert 'invest' in [r['topic'] for r in rows] and 'debt' not in [r['topic'] for r in rows]
    assert 'suitability review' in next(r for r in rows if r['topic'] == 'invest')['action']


def test_missing_planning_data_is_unavailable_not_zero():
    with SessionLocal() as db:
        organization = cards(db, 'PT Sinar Distribusi')
    for key in ('goal_progress', 'portfolio', 'debt'):
        assert organization[key]['status'] == 'UNAVAILABLE' and organization[key]['values'] == {}


def test_planning_inputs_are_covered_by_the_source_hash_and_version():
    with SessionLocal() as db:
        party = db.query(Party).filter_by(name='Dina Rahma', tenant_id='demo-bank').one()
        insight_cards(db, party)
        before = db.query(Source).filter_by(party_id=party.id, kind='BANK_DATA_SUMMARY').one()
        old_hash, old_version = before.content_hash, before.version
        db.query(BankHolding).filter_by(instrument='Reksa Dana Indeks IDX30').update({'market_value': Decimal('3000000.00')})
        db.commit()
        insight_cards(db, party)
        after = db.query(Source).filter_by(party_id=party.id, kind='BANK_DATA_SUMMARY').one()
    assert after.content_hash != old_hash and after.version == old_version + 1


def test_calendar_helpers_handle_month_ends_and_partial_months():
    assert next_payday(date(2027, 1, 31), 31) == date(2027, 2, 28)
    assert next_payday(date(2026, 12, 26), 25) == date(2027, 1, 25)
    assert months_left(date(2026, 10, 15), date(2027, 7, 1)) == 8 and months_left(date(2026, 10, 15), date(2026, 10, 1)) == 0
