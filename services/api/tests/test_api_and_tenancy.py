import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.entities import InstitutionAccessModel, UserAssignmentModel
from app.core import security

client = TestClient(app)

def h(uid='usr-maya'):
    return {'X-User-Id': uid, 'X-Tenant-Id': 'demo-bank'}

def test_anonymous_request_denied():
    assert client.get('/v1/rm/parties').status_code == 401

@pytest.mark.parametrize('token', ['usr-maya', 'test-token', 'garbage'])
def test_production_cannot_impersonate_bearer(monkeypatch, token):
    monkeypatch.setattr(security, 'ENVIRONMENT', 'production')
    assert client.get('/v1/rm/parties', headers={'Authorization': 'Bearer ' + token}).status_code == 401

def test_production_disables_header(monkeypatch):
    monkeypatch.setattr(security, 'ENVIRONMENT', 'production')
    assert client.get('/v1/rm/parties', headers=h()).status_code == 401

def test_verified_token_uses_database_membership(monkeypatch):
    with SessionLocal() as db:
        if not db.get(InstitutionAccessModel, 'demo-bank'):
            db.add(InstitutionAccessModel(tenant_id='demo-bank', status='ACTIVE', expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc)))
            db.commit()
    monkeypatch.setattr(security, 'ENVIRONMENT', 'production')
    monkeypatch.setattr(security, 'verify_firebase_token', lambda t: {'uid': 'usr-maya'})
    r = client.get('/v1/auth/me', headers={'Authorization': 'Bearer signed-token', 'X-User-Id': 'usr-maya'})
    assert r.status_code == 200
    assert r.json()['user']['role'] == 'RM'

def test_inactive_membership_denied():
    with SessionLocal() as db:
        db.query(UserAssignmentModel).filter_by(user_id='usr-maya').update({'active': False})
        db.commit()
    assert client.get('/v1/rm/parties', headers=h()).status_code == 401

def test_cross_tenant_denial():
    assert client.get('/v1/rm/parties', headers={'X-User-Id': 'usr-maya', 'X-Tenant-Id': 'other-tenant'}).status_code == 403
