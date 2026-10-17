"""Tests for LLM chat engine: multi-turn history, relaxed validators, retrieval, and failure UX."""
import json
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Turn, ChatSession
from app.services.assistant.engine import (
    ModelAnswer,
    ProviderFailure,
    LOCAL_MODEL,
    respond,
    retrieve_articles,
    validate_numbers_rule,
    fast_thinking_level,
)
from app.services.governance import resolve, DEFAULT

client = TestClient(app)

def h(user='usr-dina'):
    return {'X-User-Id': user, 'X-Tenant-Id': 'demo-bank'}

def key():
    return str(uuid.uuid4())

def pid():
    return client.get('/v1/rm/parties', headers=h()).json()['parties'][0]['id']

def create_session():
    p = pid()
    r = client.post(f"/v1/rm/chat/{p}/sessions", headers=h(), json={'request_key': key()})
    assert r.status_code == 200, r.text
    return r.json()

def send_in_session(session_id, message, **extra):
    p = pid()
    sess = client.get(f"/v1/rm/chat/{p}/sessions/{session_id}", headers=h()).json()
    return client.post(
        f"/v1/rm/chat/{p}/turns",
        headers=h(),
        json={
            'message': message,
            'base_version': sess['version'],
            'request_key': key(),
            'session_id': session_id,
            **extra,
        },
    )


# 1. Multi-turn history tests
def test_multiturn_history_passed_to_gemini(monkeypatch):
    """Multi-turn history: completed turns passed with roles user/model, customer text marked untrusted."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    captured_contents = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        if contents:
            captured_contents.append(list(contents))
        # Find a valid source id from approved_sources in payload
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        return ModelAnswer(
            answer='Everyday savings account is designed for accessible routine funds.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    sid = sess['id']

    # Turn 1
    r1 = send_in_session(sid, 'What are the savings account options?')
    assert r1.status_code == 200, r1.text
    assert r1.json()['status'] == 'COMPLETED'

    # Turn 2
    r2 = send_in_session(sid, 'Can you explain the daily transfer rules?')
    assert r2.status_code == 200, r2.text
    assert r2.json()['status'] == 'COMPLETED'

    # Turn 3 - check captured contents
    captured_contents.clear()
    r3 = send_in_session(sid, 'How about emergency funds?')
    assert r3.status_code == 200, r3.text

    assert len(captured_contents) == 1
    contents = captured_contents[0]

    # Contents should have: Turn 1 user, Turn 1 model, Turn 2 user, Turn 2 model, Turn 3 user
    assert len(contents) == 5

    # Check alternating roles
    assert contents[0].role == 'user'
    assert 'untrusted_customer_message' in contents[0].parts[0].text
    assert 'savings account options' in contents[0].parts[0].text

    assert contents[1].role == 'model'
    assert 'Everyday savings account' in contents[1].parts[0].text

    assert contents[2].role == 'user'
    assert 'untrusted_customer_message' in contents[2].parts[0].text
    assert 'daily transfer rules' in contents[2].parts[0].text

    assert contents[3].role == 'model'

    assert contents[4].role == 'user'
    assert 'emergency funds' in contents[4].parts[0].text


def test_multiturn_history_caps_at_last_8(monkeypatch):
    """History passed to Gemini is bounded to the last 8 completed turns of the session."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    captured_contents = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        if contents:
            captured_contents.append(list(contents))
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        return ModelAnswer(
            answer='Savings fact answer.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 30}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    sid = sess['id']

    # Send 9 completed turns
    for i in range(9):
        r = send_in_session(sid, f'Message turn number {i+1}')
        assert r.status_code == 200

    # Turn 10: captured contents should have at most 8 past turns (16 parts) + 1 current turn = 17 items
    captured_contents.clear()
    r10 = send_in_session(sid, 'Final turn after many messages')
    assert r10.status_code == 200

    assert len(captured_contents) == 1
    contents = captured_contents[0]
    # 8 history turns * 2 (user + model) + 1 current user turn = 17 items
    assert len(contents) == 17
    # Oldest turn in history should be turn 2, not turn 1 (turn 1 was discarded as > 8 completed turns ago)
    assert 'Message turn number 1' not in contents[0].parts[0].text
    assert 'Message turn number 2' in contents[0].parts[0].text


def test_credentials_redacted_in_history(monkeypatch):
    """Customer credentials/passwords are redacted prior to history passing."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    captured_contents = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        if contents:
            captured_contents.append(list(contents))
        valid_src = payload.get('approved_sources', [{'id': 'KB-privacy'}])[0]['id']
        return ModelAnswer(
            answer='Your privacy is protected.',
            route='PRIVACY',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 30}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    sid = sess['id']

    # Send message with a sensitive credential
    send_in_session(sid, 'my password: mysecretpass123 for the account')

    # Next turn
    captured_contents.clear()
    send_in_session(sid, 'Now tell me about security')

    assert len(captured_contents) == 1
    history_user_text = captured_contents[0][0].parts[0].text
    assert 'mysecretpass123' not in history_user_text
    assert '[redacted]' in history_user_text


# 2. Relaxed number validator tests
def test_relaxed_numbers_allows_lists_durations_years(monkeypatch):
    """List numbers, small durations <= 31, and years are allowed without source presence."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        # Answer with list numbering, 3 business days, 14 days, and year 2026
        ans_text = (
            "Here are the steps:\n"
            "1. Open your mobile app\n"
            "2. Select Savings Account\n"
            "3. Verification completes in 3 business days, or up to 14 days for special cases.\n"
            "This prototype bank policy was updated in 2026."
        )
        return ModelAnswer(
            answer=ans_text,
            route='SAVINGS',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'What are the steps to verify my savings account?')
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['status'] == 'COMPLETED'
    assert '1. Open your mobile app' in data['answer']
    assert '3 business days' in data['answer']
    assert '2026' in data['answer']


def test_relaxed_numbers_rejects_invented_monetary_amount(monkeypatch):
    """Invented monetary amounts (Rp / IDR or >= 4 digits with separators) are rejected."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        return ModelAnswer(
            answer='The administration fee for this savings account is Rp 99.000 per month.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'What is the fee?')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'FAILED'
    # Failure UX: Generic safe message shown to customer
    assert 'I could not answer that reliably' in data['answer']
    assert 'Rp 99.000' not in data['answer']
    assert 'unsupported numerical claim' not in data['answer']

    with SessionLocal() as db:
        t = db.get(Turn, data['id'])
        assert t.error_code == 'MODEL_VALIDATION_OR_TIMEOUT'
        assert 'unsupported numerical claim' in t.output_json


def test_relaxed_numbers_rejects_invented_percentage(monkeypatch):
    """Invented percentages are rejected."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-deposit'}])[0]['id']
        return ModelAnswer(
            answer='The term deposit pays a guaranteed interest rate of 8.5%.',
            route='DEPOSIT',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'What interest rate does the deposit offer?')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'FAILED'
    assert 'I could not answer that reliably' in data['answer']
    with SessionLocal() as db:
        t = db.get(Turn, data['id'])
        assert t.error_code == 'MODEL_VALIDATION_OR_TIMEOUT'


def test_numbers_match_by_value_not_digit_string():
    snapshot={'1150000.00','261666.67','27.78%'}
    for accepted in ['Transport rose to 1150000.00 IDR.','Transport rose to IDR 1,150,000.','Commitments are 261,666.67 IDR.','Spending is Rp 1.150.000.']:
        assert validate_numbers_rule(accepted,'','',snapshot)[0],accepted
    for rejected in ['Transport rose to 115,000,000 IDR.','Commitments are 261666 IDR.','Commitments are 261,666 IDR.']:
        assert not validate_numbers_rule(rejected,'','',snapshot)[0],rejected

@pytest.mark.parametrize('message,answer,card,key,shown', [
    ('Am I on track for my goals like school fees and an emergency fund?',
     'Together your two goals need IDR 2,732,142.86 a month against IDR 2,000,000 planned, and the combined shortfall is IDR 8,000,000.',
     'goal_progress', 'required_monthly_total', 'IDR 2,732,142.86'),
    ('Are there subscriptions or recurring costs I can cut?',
     'Your essential bills come to IDR 2,380,000 a month and your three transport apps to IDR 683,333.33.',
     'recurring', 'essential_total', 'IDR 2,380,000'),
])
def test_precomputed_totals_reach_the_model_and_pass_the_number_check(monkeypatch, message, answer, card, key, shown):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')
    from app.services.assistant import engine
    seen = {}

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        seen.update({c['key']: c for c in payload['permitted_context']['financial_context']})
        return ModelAnswer(answer=answer, route='SAVINGS', source_ids=[payload['approved_sources'][0]['id']]), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)
    r = send_in_session(create_session()['id'], message)
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'COMPLETED' and answer in r.json()['answer']
    assert seen[card]['values'][key] == shown

@pytest.mark.parametrize('message,route,fast,expected', [
    ('Where is my money going and how can I stop overspending?', 'SAVINGS', 'minimal', 'minimal'),
    ('How much can I safely spend or save this month without running short?', 'SAVINGS', 'minimal', 'minimal'),
    ('Am I on track for my goals like school fees and an emergency fund?', 'SAVINGS', 'minimal', 'minimal'),
    ('Are there subscriptions or recurring costs I can cut?', 'SAVINGS', 'minimal', 'minimal'),
    ('How is my overall financial health and net worth trending?', 'SAVINGS', 'minimal', 'minimal'),
    ('What product or action should I take next to improve my finances?', 'SAVINGS', 'minimal', 'minimal'),
    ('Should I pay off my credit card balance early?', 'SAVINGS', 'minimal', None),
    ('Tell me about savings accounts', 'SAVINGS', 'minimal', None),
    ('Is my portfolio performing well and what should I do next?', 'WEALTH', 'minimal', None),
    ('Why did my investments drop, is this normal, and should I sell?', 'WEALTH', 'minimal', None),
    ('Where is my money going?', 'PRIVACY', 'minimal', None),
    ('Where is my money going and how can I stop overspending?', 'SAVINGS', '', None),
])
def test_only_measured_planning_intents_use_the_fast_thinking_level(monkeypatch, message, route, fast, expected):
    monkeypatch.setenv('GEMINI_THINKING_LEVEL_FAST', fast)
    assert fast_thinking_level(message, route) == expected

def test_fast_level_reaches_the_model_and_is_recorded_on_the_turn(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL', 'low')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL_FAST', 'minimal')
    monkeypatch.delenv('GEMINI_THINKING_BUDGET', raising=False)
    from app.services.assistant import engine
    requested = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None, thinking_level=None):
        requested.append(thinking_level)
        wealth = 'portfolio' in payload['untrusted_customer_message']
        answer = "I cannot tell you whether to buy, sell or hold because that is a personal recommendation. A personal recommendation needs the bank's suitability review with an advisor." if wealth else 'Dining and transport are your largest spending categories this period.'
        return ModelAnswer(answer=answer, route='WEALTH' if wealth else 'SAVINGS', source_ids=[payload['approved_sources'][0]['id']]), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)
    spending = send_in_session(create_session()['id'], 'Where is my money going and how can I stop overspending?').json()
    wealth = send_in_session(create_session()['id'], 'Is my portfolio performing well and what should I do next?').json()
    assert requested == ['minimal', 'low']
    assert (spending['status'], spending['thinking_level']) == ('COMPLETED', 'minimal')
    assert (wealth['status'], wealth['thinking_level']) == ('COMPLETED', 'low')
def test_cascade_retries_with_low_when_minimal_fails_validation(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL', 'minimal')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL_FALLBACK', 'low')
    monkeypatch.delenv('GEMINI_THINKING_BUDGET', raising=False)
    monkeypatch.delenv('GEMINI_THINKING_LEVEL_FAST', raising=False)
    from app.services.assistant import engine
    calls = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None, thinking_level=None):
        calls.append(thinking_level)
        if thinking_level == 'minimal':
            ans = 'Your transport costs were IDR 999,999,999.'  # Unsupported number -> validation fails
        else:
            ans = 'Dining and transport are your largest spending categories this period.'
        return ModelAnswer(answer=ans, route='SAVINGS', source_ids=[payload['approved_sources'][0]['id']]), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)
    turn = send_in_session(create_session()['id'], 'Where is my money going and how can I stop overspending?').json()
    assert turn['status'] == 'COMPLETED'
    assert turn['thinking_level'] == 'minimal->low'
    assert calls == ['minimal', 'low']
    assert 'Dining and transport' in turn['answer']

def test_cascade_returns_minimal_when_first_attempt_succeeds(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL', 'minimal')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL_FALLBACK', 'low')
    monkeypatch.delenv('GEMINI_THINKING_BUDGET', raising=False)
    monkeypatch.delenv('GEMINI_THINKING_LEVEL_FAST', raising=False)
    from app.services.assistant import engine
    calls = []

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None, thinking_level=None):
        calls.append(thinking_level)
        return ModelAnswer(answer='Dining and transport are your largest spending categories this period.', route='SAVINGS', source_ids=[payload['approved_sources'][0]['id']]), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)
    turn = send_in_session(create_session()['id'], 'Where is my money going and how can I stop overspending?').json()
    assert turn['status'] == 'COMPLETED'
    assert turn['thinking_level'] == 'minimal'
    assert calls == ['minimal']


def test_follow_up_suggestions_drop_numbers_links_and_promises(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')
    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        return ModelAnswer(
            answer='An everyday savings account keeps money accessible for routine payments.',
            route='SAVINGS',
            source_ids=[payload['approved_sources'][0]['id']],
            suggestions=['Show my recurring bills', 'Save IDR 500,000 every month', 'Is a guaranteed return possible?', 'show my recurring bills', 'Open www.example.com', 'Help me plan my shopping budget'],
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)
    r = send_in_session(create_session()['id'], 'What is a savings account?')
    assert r.status_code == 200, r.text
    assert r.json()['suggestions'] == ['Show my recurring bills', 'Help me plan my shopping budget']

# 3. Paraphrased need tests
def test_paraphrased_need_keeps_answer_and_drops_need_and_signal(monkeypatch):
    """When need is not an exact customer span, drop need without failing the turn, no signal."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        # Model paraphrases need: not an exact substring of "Tell me about savings account options"
        return ModelAnswer(
            answer='An everyday savings account is intended for accessible money and routine payments.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='Customer wants to open a high yield savings account',
            explicit_interest=True,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'Tell me about savings account options')
    assert r.status_code == 200
    data = r.json()
    # Answer is kept!
    assert data['status'] == 'COMPLETED'
    assert 'accessible money' in data['answer']
    # No signal created because need was dropped and explicit_interest was cleared
    assert data['signal_id'] is None


def test_human_help_request_creates_guidance_signal_from_own_words(monkeypatch):
    """Human-help requests create guidance signal from the customer's own words."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        return ModelAnswer(
            answer='You can discuss your savings requirements with an authorized RM.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='paraphrased need that gets dropped',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'I want to speak to my RM about setting up savings')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'COMPLETED'
    # Signal is created from customer's own words!
    assert data['signal_id'] is not None


# 4. Governance route mismatch and privacy routing tests
def test_governance_route_mismatch_kept_and_recorded(monkeypatch):
    """When model route differs from pinned governance route, keep governance route and record mismatch."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        # Model returns DEPOSIT while pinned governance route is SAVINGS
        valid_src = payload.get('approved_sources', [{'id': 'KB-deposit'}])[0]['id']
        return ModelAnswer(
            answer='A term deposit holds money for an agreed maturity period.',
            route='DEPOSIT',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    # Message triggers SAVINGS governance rule
    r = send_in_session(sess['id'], 'I want to save for my emergency fund')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'COMPLETED'
    # Governance route kept
    assert data['route'] == 'SAVINGS'
    with SessionLocal() as db:
        t = db.get(Turn, data['id'])
        out = json.loads(t.output_json)
        assert 'route_mismatch' in out
        assert out['route_mismatch']['expected'] == 'SAVINGS'
        assert out['route_mismatch']['actual'] == 'DEPOSIT'


def test_privacy_routing_stays_hard(monkeypatch):
    """Privacy route mismatch fails validation."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_structured_generate(system, payload, schema, *, max_output_tokens, contents=None):
        valid_src = payload.get('approved_sources', [{'id': 'KB-savings'}])[0]['id']
        return ModelAnswer(
            answer='Savings account information.',
            route='SAVINGS',
            source_ids=[valid_src],
            need='',
            explicit_interest=False,
        ), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 50}

    monkeypatch.setattr(engine, 'structured_generate', mock_structured_generate)

    sess = create_session()
    r = send_in_session(sess['id'], 'Stop contacting me, do not contact')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'FAILED'
    assert 'I could not answer that reliably' in data['answer']
    with SessionLocal() as db:
        t = db.get(Turn, data['id'])
        assert t.error_code == 'MODEL_VALIDATION_OR_TIMEOUT'
        assert 'privacy routing validation' in t.output_json


# 5. Failure UX tests
def test_failure_ux_shows_safe_message_not_internal_validator_error(monkeypatch):
    """Never show internal validator error string to customer; store error_code and error in trace."""
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key-for-test')

    from app.services.assistant import engine

    def mock_fail(*args, **kwargs):
        raise ProviderFailure('Internal validator failure: exact span regex failed.')

    monkeypatch.setattr(engine, 'structured_generate', mock_fail)

    sess = create_session()
    r = send_in_session(sess['id'], 'What is a term deposit?')
    assert r.status_code == 200
    data = r.json()
    assert data['status'] == 'FAILED'
    # Helpful safe message
    assert data['answer'] == 'I could not answer that reliably. You can rephrase, or ask for your RM through the official channel.'
    assert 'Internal validator failure' not in data['answer']

    with SessionLocal() as db:
        t = db.get(Turn, data['id'])
        assert t.error_code == 'MODEL_VALIDATION_OR_TIMEOUT'
        out = json.loads(t.output_json)
        assert 'Internal validator failure' in out.get('error', '')


# 6. Retrieval tests
def test_knowledge_retrieval_scoring_and_top_k():
    """Retrieval selects top-k (<=5) articles by keyword scoring over title+body and keeps route."""
    raw_kb = json.loads(Path('data/synthetic/rm/knowledge.json').read_text())
    kb = {item['key']: {'id': 'KB-' + item['key'], 'title': item['title'], 'content': item['body'], 'topics': item.get('topics', [])} for item in raw_kb}

    # Query about BI-FAST limits
    results = retrieve_articles('What is the daily transfer limit for BI-FAST?', kb, route='SERVICE', top_k=5)
    assert len(results) <= 5
    # The bifast article should be retrieved
    titles = [r['title'] for r in results]
    assert any('BI-FAST' in t for t in titles)

    # Privacy query always includes privacy article
    priv_results = retrieve_articles('Please stop contacting me and respect my privacy', kb, route='PRIVACY', top_k=5)
    assert any('privacy' in r['id'].lower() for r in priv_results)


# 7. Comprehensive evaluation cases test
def test_all_evaluation_cases_pass():
    """All 30 evaluation cases in evaluation.json pass under local simulation."""
    cases = json.loads(Path('data/synthetic/rm/evaluation.json').read_text())
    raw_kb = json.loads(Path('data/synthetic/rm/knowledge.json').read_text())
    kb = {item['key']: {'id': 'KB-' + item['key'], 'title': item['title'], 'content': item['body'], 'topics': item.get('topics', [])} for item in raw_kb}

    assert len(cases) == 30, f"Expected 30 cases (24 original + 6 new), got {len(cases)}"

    for c in cases:
        ans = respond(
            c['question'],
            '',
            kb,
            {
                'name': 'Synthetic evaluation person',
                'declared_goal': '',
                'mode': 'SYNTHETIC',
                'governance_context': resolve(DEFAULT, c['question']),
            },
        )
        qa = ans.route == c['route'] and c['contains'].casefold() in ans.text.casefold()
        tools = (
            ans.route == c['route']
            and {x['name'] for x in ans.tools}
            == (
                {'read_approved_knowledge', 'read_permitted_customer_context'}
                if c['tools'] == 2
                else {'read_approved_knowledge'}
            )
        )
        assert qa, f"Case {c['id']} failed QA: route={ans.route} vs {c['route']}, contains='{c['contains']}' in '{ans.text}'"
        assert tools, f"Case {c['id']} failed Tools check: {[t['name'] for t in ans.tools]}"
