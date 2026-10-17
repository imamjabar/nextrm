import json, uuid, hashlib, os
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.relationships import Party, Signal, Source, Journey
from app.models.relationships import ReviewEvent
from app.models.entities import utc_now
from app.services.assistant.engine import structured_generate, ProviderFailure, ProviderUnavailable, PROMPT_BRIEF_VERSION, PROMPT_DRAFT_VERSION

c = TestClient(app)

def h(uid='usr-maya', tenant='demo-bank'):
    return {'X-User-Id': uid, 'X-Tenant-Id': tenant}

def people():
    return c.get('/v1/rm/parties', headers=h()).json()['parties']

def dina():
    return next(x for x in people() if x['name'] == 'Dina Rahma')

def setup_followup(contact='ALLOWED', category='OPPORTUNITY', need='Discuss savings options'):
    with SessionLocal() as db:
        p = db.get(Party, dina()['id'])
        p.contact = contact
        src = Source(
            id='SRC-' + uuid.uuid4().hex[:12],
            tenant_id='demo-bank',
            party_id=p.id,
            title='Customer Statement',
            content='I want to discuss options for 2026.',
            kind='CUSTOMER_MESSAGE',
            mode='SIMULATED',
            version=1,
            content_hash=hashlib.sha256('I want to discuss options for 2026.'.encode()).hexdigest(),
            event_at=utc_now(),
            ingested_at=utc_now()
        )
        db.add(src)
        db.flush()
        sig = Signal(
            id='SIG-' + uuid.uuid4().hex[:12],
            tenant_id='demo-bank',
            party_id=p.id,
            source_id=src.id,
            owner_id='usr-maya',
            semantic_key='test-key-' + uuid.uuid4().hex[:8],
            category=category,
            urgency='ROUTINE',
            evidence='CUSTOMER_CONFIRMED',
            workflow='IN_PROGRESS',
            review='ACCEPTED',
            title='Savings Need',
            need=need,
            rationale='Review rationale',
            uncertainty='Low',
            confirmed=True,
            version=1
        )
        db.add(sig)
        db.flush()
        journey = Journey(
            id='FOL-' + uuid.uuid4().hex[:12],
            tenant_id='demo-bank',
            party_id=p.id,
            actor_id='usr-maya',
            source_id=src.id,
            signal_id=sig.id,
            kind='RM_FOLLOWUP',
            request_key=str(uuid.uuid4()),
            payload_hash='hash',
            need=need,
            status='PLANNED',
            operation_ref='TASK-001',
            draft='Initial placeholder draft'
        )
        db.add(journey)
        db.commit()
        return journey.id, src.id, p.id


def test_rm_gets_simulated_brief_with_valid_citations():
    p = dina()
    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['party_id'] == p['id']
    assert data['mode'] == 'SIMULATED'
    assert data['model'] == 'local-governed-engine-v1.5'
    assert data['prompt_version'] == 'rm-brief-v1'
    assert data['summary']
    assert len(data['talking_points']) > 0
    assert len(data['talking_points']) <= 5
    assert len(data['questions']) <= 4
    assert len(data['cautions']) <= 4

    source_ids = {s['id'] for s in data['sources']}
    for tp in data['talking_points']:
        assert len(tp['source_ids']) >= 1
        for sid in tp['source_ids']:
            assert sid in source_ids

    with SessionLocal() as db:
        event = db.query(ReviewEvent).filter_by(action='AI_BRIEF_GENERATED', resource_id=p['id']).first()
        assert event is not None
        assert event.actor_id == 'usr-maya'
        assert event.tenant_id == 'demo-bank'
        meta = json.loads(event.after_json)
        assert meta['mode'] == 'SIMULATED' and meta['prompt_version'] == PROMPT_BRIEF_VERSION and meta['source_ids']
        assert data['summary'] not in event.after_json


def test_customer_and_admin_cannot_access_ai_brief_or_draft():
    p = dina()
    fid, _, _ = setup_followup()

    for user in ['usr-dina', 'usr-aiadmin', 'usr-quality']:
        assert c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h(user)).status_code == 403
        assert c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h(user), json={'channel': 'EMAIL'}).status_code == 403


def test_other_rm_party_and_followup_denied():
    p = dina()
    fid, _, _ = setup_followup()

    with SessionLocal() as db:
        db.get(Party, p['id']).owner_id = 'other-rm'
        db.commit()

    # Maya no longer owns Dina's relationship
    assert c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya')).status_code == 403

    # Reassign follow-up ownership to another user
    with SessionLocal() as db:
        db.get(Journey, fid).actor_id = 'other-rm'
        db.commit()

    assert c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'}).status_code == 403


def test_draft_gate_409_for_restricted_commercial_contact():
    fid, _, pid = setup_followup(contact='RESTRICTED', category='OPPORTUNITY', need='Commercial loan follow-up')

    # Commercial follow-up with RESTRICTED contact must be rejected with 409
    r = c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r.status_code == 409
    assert r.json()['detail'] == "Commercial contact is restricted for this customer; service help remains available."

    with SessionLocal() as db:
        row = db.get(Journey, fid)
        assert row.draft == 'Initial placeholder draft'  # Never writes Journey.draft

    # Now make the signal a SERVICE_ISSUE on the same restricted customer
    service_fid, _, _ = setup_followup(contact='RESTRICTED', category='SERVICE_ISSUE', need='Recipient cannot see my transfer')
    r_service = c.post(f"/v1/rm/follow-ups/{service_fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r_service.status_code == 200, r_service.text
    data = r_service.json()
    assert data['boundary'] == "Draft only — not sent. Review and send through the bank's official channel."
    assert data['mode'] == 'SIMULATED'
    assert data['followup_id'] == service_fid
    assert len(data['source_ids']) >= 1
    assert len(data['sources']) >= 1

    with SessionLocal() as db:
        row = db.get(Journey, service_fid)
        assert row.draft == 'Initial placeholder draft'  # Never writes Journey.draft
        audit = db.query(ReviewEvent).filter_by(action='AI_DRAFT_GENERATED', resource_id=service_fid).first()
        assert audit is not None


def test_vertex_provider_without_config_returns_503_no_fallback(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.delenv('GOOGLE_CLOUD_PROJECT', raising=False)
    monkeypatch.delenv('GOOGLE_CLOUD_LOCATION', raising=False)

    p = dina()
    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 503
    assert 'No local fallback' in r.json()['detail']

    with SessionLocal() as db:
        failed = db.query(ReviewEvent).filter_by(action='AI_BRIEF_FAILED', resource_id=p['id']).first()
        assert failed is not None
        assert failed.actor_id == 'usr-maya'

    fid, _, _ = setup_followup()
    r2 = c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r2.status_code == 503
    assert 'No local fallback' in r2.json()['detail']

    with SessionLocal() as db:
        failed2 = db.query(ReviewEvent).filter_by(action='AI_DRAFT_FAILED', resource_id=fid).first()
        assert failed2 is not None


def test_validator_rejects_uncited_and_unknown_source(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-proj')
    monkeypatch.setenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')

    class FakePointUnknown:
        text = "Customer has a question."
        source_ids = ["bogus-source-id-999"]

    class FakeBriefUnknown:
        summary = "Summary statement."
        talking_points = [FakePointUnknown()]
        questions = ["Question?"]
        cautions = ["Caution."]

    monkeypatch.setattr('app.routers.enrichment.generate_ai_brief', lambda *a, **kw: None) # ensure structured_generate path
    # monkeypatch structured_generate directly in engine
    from app.services.assistant import engine
    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeBriefUnknown(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 30}))

    p = dina()
    # Re-import or ensure enrichment uses the patched engine
    from app.routers import enrichment
    monkeypatch.setattr(enrichment, 'generate_ai_brief', engine.generate_ai_brief)

    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 502
    assert 'no simulated fallback' in r.json()['detail'].lower()

    with SessionLocal() as db:
        failed = db.query(ReviewEvent).filter_by(action='AI_BRIEF_FAILED', resource_id=p['id']).first()
        assert failed is not None


def test_validator_rejects_unsupported_number_in_live_output(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-proj')
    monkeypatch.setenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')

    p = dina()
    b = c.get(f"/v1/rm/parties/{p['id']}/brief", headers=h('usr-maya')).json()
    real_src_id = b['facts'][0]['source']['id']

    class FakePointNum:
        text = "Customer balance grew by 99.9%."
        source_ids = [real_src_id]

    class FakeBriefNum:
        summary = "Customer review with unsupported 88888."
        talking_points = [FakePointNum()]
        questions = []
        cautions = []

    from app.services.assistant import engine
    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeBriefNum(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 35}))
    from app.routers import enrichment
    monkeypatch.setattr(enrichment, 'generate_ai_brief', engine.generate_ai_brief)

    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 502
    assert 'no simulated fallback' in r.json()['detail'].lower()


def test_validator_rejects_banned_phrases_and_urls(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-proj')
    monkeypatch.setenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')

    p = dina()
    b = c.get(f"/v1/rm/parties/{p['id']}/brief", headers=h('usr-maya')).json()
    real_src_id = b['facts'][0]['source']['id']

    class FakePointBanned:
        text = "Loan approved and guaranteed return."
        source_ids = [real_src_id]

    class FakeBriefBanned:
        summary = "Summary statement."
        talking_points = [FakePointBanned()]
        questions = []
        cautions = []

    from app.services.assistant import engine
    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeBriefBanned(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 35}))
    from app.routers import enrichment
    monkeypatch.setattr(enrichment, 'generate_ai_brief', engine.generate_ai_brief)

    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 502

    class FakePointUrl:
        text = "Visit https://bank.example.com for more information."
        source_ids = [real_src_id]

    class FakeBriefUrl:
        summary = "Summary statement."
        talking_points = [FakePointUrl()]
        questions = []
        cautions = []

    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeBriefUrl(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 35}))
    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 502


def test_live_structured_generate_success_when_valid(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-proj')
    monkeypatch.setenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')

    p = dina()
    b = c.get(f"/v1/rm/parties/{p['id']}/brief", headers=h('usr-maya')).json()
    real_src_id = b['facts'][0]['source']['id']
    real_src_text = b['facts'][0]['source']['content']

    class FakePointValid:
        text = real_src_text
        source_ids = [real_src_id]

    class FakeBriefValid:
        summary = "Grounded relationship brief."
        talking_points = [FakePointValid()]
        questions = ["What timing constraints exist?"]
        cautions = ["Review before outreach."]

    from app.services.assistant import engine
    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeBriefValid(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 110}))
    from app.routers import enrichment
    monkeypatch.setattr(enrichment, 'generate_ai_brief', engine.generate_ai_brief)

    r = c.post(f"/v1/rm/parties/{p['id']}/ai-brief", headers=h('usr-maya'))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['mode'] == 'LIVE'
    assert data['model'] == 'gemini-2.5-flash'
    assert data['prompt_version'] == 'rm-brief-v1'
    assert data['sources'][0]['id'] == real_src_id


def test_live_draft_validator_and_success(monkeypatch):
    monkeypatch.setenv('NEXTRM_AI_PROVIDER', 'vertex')
    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'test-proj')
    monkeypatch.setenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-2.5-flash')

    fid, sid, _ = setup_followup(contact='ALLOWED', category='OPPORTUNITY', need='Discuss savings options')

    class FakeDraftInvalidSource:
        subject = "Hello"
        body = "Following up on your request."
        source_ids = ["unauthorized-source"]

    from app.services.assistant import engine
    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeDraftInvalidSource(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 40}))
    from app.routers import engagement
    monkeypatch.setattr(engagement, 'generate_ai_draft', engine.generate_ai_draft)

    r = c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r.status_code == 502

    class FakeDraftInvalidNum:
        subject = "Rate 15% guaranteed"
        body = "We offer 15% rate."
        source_ids = [sid]

    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeDraftInvalidNum(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 40}))
    r = c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r.status_code == 502

    class FakeDraftValid:
        subject = "Following up on your request"
        body = "I would be glad to discuss your requirements for 2026."
        source_ids = [sid]

    monkeypatch.setattr(engine, 'structured_generate', lambda sys, pay, schema, **kw: (FakeDraftValid(), {'mode': 'LIVE', 'model': 'gemini-2.5-flash', 'latency_ms': 95}))
    r = c.post(f"/v1/rm/follow-ups/{fid}/ai-draft", headers=h('usr-maya'), json={'channel': 'EMAIL'})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['mode'] == 'LIVE'
    assert data['model'] == 'gemini-2.5-flash'
    assert data['boundary'] == "Draft only — not sent. Review and send through the bank's official channel."
