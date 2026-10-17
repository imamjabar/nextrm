"""Customer chat for money-planning and investment-context questions: routing, suitability boundary, validators, scope."""
import json
import re
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Party, Turn
from app.services.assistant import engine
from app.services.assistant.engine import ModelAnswer, breaks_investment_rules, clean_suggestions
from app.services.assistant.planning_answers import select_context
from app.services.enrichment import insights_for
from app.services.governance import DEFAULT, resolve, test_definition as policy_self_test

client = TestClient(app)


def h(user='usr-dina'):
    return {'X-User-Id': user, 'X-Tenant-Id': 'demo-bank'}


def person():
    return client.get('/v1/rm/parties', headers=h()).json()['parties'][0]['id']


def ask(message):
    p = person()
    session = client.post(f'/v1/rm/chat/{p}/sessions', headers=h(), json={'request_key': str(uuid.uuid4())}).json()
    version = client.get(f'/v1/rm/chat/{p}/sessions/{session["id"]}', headers=h()).json()['version']
    r = client.post(f'/v1/rm/chat/{p}/turns', headers=h(), json={'message': message, 'base_version': version, 'request_key': str(uuid.uuid4()), 'session_id': session['id']})
    assert r.status_code == 200, r.text
    return r.json()


def route_of(question, previous=''):
    return resolve(DEFAULT, question, previous)['route']


@pytest.mark.parametrize('question,route', [
    ('Where is my money going and how can I stop overspending?', 'SAVINGS'),
    ('How much can I safely spend this month?', 'SAVINGS'),
    ('How do I start investing with limited money?', 'WEALTH'),
    ('Am I on track for my school fund goal?', 'SAVINGS'),
    ('Is my portfolio performing well and what should I do next?', 'WEALTH'),
    ('Should I pay down my credit card or save more?', 'SAVINGS'),
    ('Should I pay off my credit card or invest extra cash?', 'WEALTH'),
    ('Are there subscriptions or recurring costs I can cut?', 'SAVINGS'),
    ('What product or action should I take next to improve my finances?', 'SAVINGS'),
    ('How is my overall financial health and net worth trending?', 'SAVINGS'),
    ('Why did my investments drop and should I sell?', 'WEALTH'),
    ('Cancel my Netflix subscription', 'SAVINGS'),
    ('How do I pay my credit card bill?', 'CARD'),
    ('I lost my card', 'CARD'),
    ('I want a loan to pay off my credit card', 'LOAN'),
])
def test_questions_reach_the_route_that_owns_them(question, route):
    assert route_of(question) == route


def test_follow_up_to_an_investment_answer_keeps_the_investment_route_and_its_context():
    decision = resolve(DEFAULT, 'Should I sell?', 'WEALTH')
    assert decision['route'] == 'WEALTH' and 'READ_FINANCIAL_CONTEXT' in decision['steps']
    assert route_of('Should I sell?') != 'WEALTH'


def test_investment_decisions_carry_the_suitability_guardrails():
    asked = resolve(DEFAULT, 'Should I sell my fund and buy more stock?')
    assert asked['advice_requested'] and 'NO_PERSONAL_INVESTMENT_RECOMMENDATION' in asked['guardrails'] and 'NO_RISK_TOLERANCE_INFERENCE' in asked['guardrails']
    assert not resolve(DEFAULT, 'How is my portfolio doing?')['advice_requested']
    assert 'guardrails' not in resolve(DEFAULT, 'Where is my money going?')


def test_default_policy_examples_all_resolve_to_their_declared_route():
    results = policy_self_test(DEFAULT)
    assert results and all(x['passed'] for x in results), [x for x in results if not x['passed']]


@pytest.mark.parametrize('question,facts', [
    ('Where is my money going and how can I stop overspending?', ['IDR 6,035,000', 'Groceries', '27.78%']),
    ('How much can I safely spend this month?', ['IDR 10,643,888.89', '25 Oct 2026']),
    ('Am I on track for my goals?', ['IDR 1,875,000', 'IDR 375,000', 'Dana Pendidikan Anak']),
    ('Is my portfolio performing well and what should I do next?', ['IDR 10,399,000', '-0.96%']),
    ('Should I pay down my credit card or invest extra cash?', ['IDR 84,000', 'IDR 8,750', '26 months']),
    ('Are there subscriptions or recurring costs I can cut?', ['Spotify AB', 'Restoran Padang Sederhana']),
    ('What product or action should I take next to improve my finances?', ['Pay off your credit card balance']),
    ('How is my overall financial health and net worth trending?', ['IDR 18,699,000', '34.49%']),
    ('Why did my investments drop and should I sell?', ['down 6.10%', '3.4%']),
])
def test_simulated_engine_answers_from_validated_figures_and_never_advises(question, facts):
    turn = ask(question)
    assert turn['status'] == 'COMPLETED' and turn['mode'] == 'SIMULATED' and {s['kind'] for s in turn['sources']} & {'BANK_DATA_SUMMARY', 'APPROVED_KNOWLEDGE'}
    for fact in facts:
        assert fact in turn['answer'], (fact, turn['answer'])
    assert not breaks_investment_rules(turn['answer'])
    assert not re.search(r'\d{7,}\.\d\d', turn['answer'])


def test_investment_answers_state_the_boundary_and_offer_the_relationship_manager():
    answer = ask('Why did my investments drop and should I sell?')['answer']
    assert 'not enabled' in answer and 'suitability review with an advisor' in answer and 'relationship manager' in answer


def test_asking_for_the_rm_after_an_investment_answer_reaches_the_rm_queue_as_guidance():
    turn = ask('Talk to my RM about my portfolio')
    assert turn['status'] == 'COMPLETED' and turn['signal_id']
    signals = client.get('/v1/rm/signals', headers=h('usr-maya')).json()['signals']
    assert next(x for x in signals if x['id'] == turn['signal_id'])['category'] == 'GUIDANCE'


def with_live_model(monkeypatch, answer, route='WEALTH', capture=None):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-test')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    def generate(system, payload, schema, *, max_output_tokens, contents=None):
        if capture is not None:
            capture.append(payload)
        return ModelAnswer(answer=answer, route=route, source_ids=[payload['approved_sources'][0]['id']], suggestions=['Talk to my RM about my portfolio']), {'mode': 'LIVE', 'model': 'gemini-test', 'latency_ms': 5}

    monkeypatch.setattr(engine, 'structured_generate', generate)


def failure_reason(turn):
    with SessionLocal() as db:
        return json.loads(db.get(Turn, turn['id']).output_json)['error']


def test_live_answer_may_describe_a_loss_without_repeating_the_minus_sign(monkeypatch):
    with_live_model(monkeypatch, "Your index fund is down 6.10% over 30 days, a loss of IDR 215,000 for the whole portfolio. A personal recommendation needs the bank's suitability review with an advisor.")
    turn = ask('Why did my investments drop?')
    assert turn['status'] == 'COMPLETED' and turn['mode'] == 'LIVE'


@pytest.mark.parametrize('text,violation', [
    ('You should sell your equity fund now.', True),
    ('It is better to hold your equity fund.', True),
    ('You should not sell in a panic.', True),
    ('The fund will rebound next month.', True),
    ('Do not worry, the market will recover soon.', True),
    ("I can't tell you whether you should sell or hold; that needs the bank's suitability review with an advisor.", False),
    ('No one can predict whether the market will recover.', False),
    ('It is best to speak with your relationship manager before you decide to sell.', False),
    ('Equity funds can fall as well as rise, and selling after a fall makes a loss permanent.', False),
])
def test_advice_detector_flags_directives_and_predictions_but_not_boundary_statements(text, violation):
    assert breaks_investment_rules(text) is violation


@pytest.mark.parametrize('answer,reason', [
    ('You should sell your equity fund now.', 'personal investment recommendation'),
    ('I recommend you switch into a bond fund.', 'personal investment recommendation'),
    ('Do not worry, the market will recover soon.', 'personal investment recommendation or a market prediction'),
    ('It is better to hold your equity fund.', 'personal investment recommendation'),
    ('Your portfolio is worth IDR 99,999,999 today.', 'unsupported numerical claim'),
    ('Your fund is down 42.50% this month.', 'Unsupported percentage'),
])
def test_live_answers_that_advise_predict_or_invent_numbers_fail_closed(monkeypatch, answer, reason):
    with_live_model(monkeypatch, answer)
    turn = ask('Why did my investments drop?')
    assert turn['status'] == 'FAILED' and 'could not answer that reliably' in turn['answer']
    assert reason in failure_reason(turn)


def test_live_model_only_receives_the_cards_that_serve_the_question(monkeypatch):
    seen = []
    with_live_model(monkeypatch, "Your portfolio is worth IDR 10,399,000. A personal recommendation needs the bank's suitability review with an advisor.", capture=seen)
    ask('Why did my investments drop?')
    portfolio_keys = {c['key'] for c in seen[0]['permitted_context']['financial_context']}
    assert {'portfolio', 'goal_progress', 'safe_to_spend'} <= portfolio_keys and not portfolio_keys & {'debt', 'next_actions', 'net_worth', 'recurring'}
    assert seen[0]['permitted_context']['governance']['guardrails'] and seen[0]['untrusted_customer_message'] == 'Why did my investments drop?'
    with_live_model(monkeypatch, 'Your first step is the card balance of IDR 4,200,000.', route='SAVINGS', capture=seen)
    ask('What product or action should I take next to improve my finances?')
    assert {'next_actions', 'debt', 'portfolio'} <= {c['key'] for c in seen[1]['permitted_context']['financial_context']}


def test_questions_outside_planning_keep_the_original_insight_scope():
    with SessionLocal() as db:
        party = db.query(Party).filter_by(name='Dina Rahma', tenant_id='demo-bank').one()
        everything = insights_for(db, party, {})
        db.commit()
    scoped = {c['key'] for c in select_context(everything, 'How does a time deposit work?', 'DEPOSIT')}
    assert scoped == {'cash_flow', 'spending', 'recurring', 'salary', 'idle_cash', 'term_deposit', 'balance_trend'}


def test_suggestion_chips_never_ask_the_assistant_to_act():
    chips = ['Pay off my credit card', 'Transfer money to savings', 'Talk to my RM about my portfolio', 'Show my goal progress', 'Open a time deposit']
    assert clean_suggestions(chips) == ['Talk to my RM about my portfolio', 'Show my goal progress']
