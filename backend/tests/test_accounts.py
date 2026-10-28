"""Self-service accounts must never grant access to another user's projects."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.endpoints.metrics import router as metrics_router
from app.models.request import Request as RequestRecord
from app.models.cache_event import CacheEvent, CacheStatus
from app.api.endpoints.accounts import router
from app.api.endpoints.projects import router as admin_router
from app.api.endpoints.workspaces import router as workspace_router
from app.core import auth
from app.database.base import Base
from app.database.session import get_db
from app.models.account import AuthAttempt, User, UserSession
from app.models.project import ProjectAPIKey
from app.services.api_keys import authenticate_project_key


@pytest.fixture
def account_app(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    def db():
        with factory() as session:
            yield session
    class Manager:
        @contextmanager
        def session_scope(self):
            with factory() as session:
                yield session
                session.commit()
    monkeypatch.setattr(auth, 'get_db_manager', lambda: Manager())
    monkeypatch.setattr(auth.settings, 'REQUIRE_API_KEY', True)
    monkeypatch.setattr(auth.settings, 'API_KEY', 'admin-secret')
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    app.include_router(admin_router, prefix='/api/v1')
    app.include_router(metrics_router, prefix='/api/v1')
    app.include_router(workspace_router, prefix='/api/v1')
    app.dependency_overrides[get_db] = db
    @app.get('/metrics-scope')
    def scope(context=Depends(auth.verify_metrics_key)):
        return {'tenant_id': context.tenant_id, 'is_admin': context.is_admin}
    @app.get('/application-scope')
    def app_scope(context=Depends(auth.verify_api_key)):
        return {'tenant_id': context.tenant_id}
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def register(client, email):
    response = client.post('/api/v1/account/register', json={'email': email, 'password': 'a-strong-password-123'})
    assert response.status_code == 201, response.text
    assert response.headers['cache-control'] == 'no-store'
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_users_create_keys_and_are_isolated(account_app):
    client, factory = account_app
    alice = register(client, 'Alice@example.com')
    bob = register(client, 'bob@example.com')
    response = client.post('/api/v1/account/projects', headers=alice, json={'name': 'Alice bot'})
    assert response.status_code == 201
    created = response.json()
    project_id, raw = created['project_id'], created['api_key']
    assert raw.startswith('dc_live_')
    with factory() as db:
        user = db.query(User).filter_by(email='alice@example.com').one()
        assert user.password_hash.startswith('pbkdf2_sha256$')
        assert 'a-strong-password-123' not in user.password_hash
        assert db.query(ProjectAPIKey).one().key_hash != raw
        assert authenticate_project_key(db, raw).tenant_id == created['tenant_id']
    assert client.get('/api/v1/account/projects', headers=bob).json() == []
    path = f'/api/v1/account/projects/{project_id}/keys'
    for method, url, body in [('get', path, None), ('post', path, {'name': 'stolen'}), ('delete', path+'/'+created['api_key_id'], None)]:
        assert client.request(method, url, headers=bob, json=body).status_code == 404
    listed = client.get(path, headers=alice).json()
    assert 'api_key' not in listed[0] and 'key_hash' not in listed[0]
    scoped_headers = {**alice, 'X-Project-ID': project_id}
    assert client.get('/metrics-scope', headers=scoped_headers, params={'tenant_id': 'default'}).json() == {
        'tenant_id': created['tenant_id'], 'is_admin': False}
    assert client.get('/metrics-scope', headers={**bob, 'X-Project-ID': project_id}).status_code == 404
    assert client.get('/metrics-scope', headers=alice).status_code == 404
    assert client.get('/api/v1/projects', headers=alice).status_code == 403
    assert client.get('/application-scope', headers=alice).status_code == 401
    assert client.get('/application-scope', headers={'Authorization': 'Bearer '+raw}).status_code == 200
    replacement = client.post(path, headers=alice, json={'name': 'rotated'}).json()
    assert replacement['api_key'] != raw
    assert client.delete(path+'/'+created['api_key_id'], headers=alice).status_code == 204
    assert client.get('/application-scope', headers={'Authorization': 'Bearer '+raw}).status_code == 401
    assert client.get('/application-scope', headers={'Authorization': 'Bearer '+replacement['api_key']}).status_code == 200


def test_login_logout_expiry_and_invalid_credentials(account_app):
    client, factory = account_app
    headers = register(client, 'alice@example.com')
    assert client.post('/api/v1/account/register', json={'email': ' ALICE@example.com ', 'password': 'another-password'}).status_code == 409
    for email in ['alice@example.com', 'missing@example.com']:
        result = client.post('/api/v1/account/login', json={'email': email, 'password': 'wrong-password-123'})
        assert result.status_code == 401 and result.json()['detail'] == 'Incorrect email or password'
    assert client.post('/api/v1/account/register', json={'email': 'invalid', 'password': 'short'}).status_code == 422
    assert client.post('/api/v1/account/logout', headers=headers).status_code == 204
    assert client.get('/api/v1/account/me', headers=headers).status_code == 401
    response = client.post('/api/v1/account/login', json={'email': 'ALICE@example.com', 'password': 'a-strong-password-123'})
    assert response.status_code == 200
    login = {'Authorization': 'Bearer '+response.json()['token']}
    assert client.get('/api/v1/account/me', headers=login).json()['email'] == 'alice@example.com'
    with factory() as db:
        session = db.query(UserSession).one()
        assert session.token_hash != response.json()['token']
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get('/api/v1/account/projects', headers=login).status_code == 401
    assert client.post('/api/v1/account/projects', headers={'Authorization': 'Bearer admin-secret'}, json={'name': 'bad'}).status_code == 401


def test_auth_rate_limit_is_persisted(account_app):
    client, factory = account_app
    register(client, 'one@example.com')
    with factory() as db:
        attempt = db.query(AuthAttempt).one()
        db.add_all([AuthAttempt(client_hash=attempt.client_hash, created_at=datetime.now(timezone.utc)) for _ in range(19)])
        db.commit()
    result = client.post('/api/v1/account/login', json={'email': 'one@example.com', 'password': 'a-strong-password-123'})
    assert result.status_code == 429
    assert result.headers['retry-after'] == '900'


def test_dashboard_and_request_history_only_show_selected_owned_application(account_app):
    client, factory = account_app
    alice = register(client, 'alice@example.com')
    bob = register(client, 'bob@example.com')
    apps = [client.post('/api/v1/account/projects', headers=owner, json={'name': name}).json()
            for owner, name in [(alice, 'Alice bot'), (alice, 'Alice second bot'), (bob, 'Bob private bot')]]
    with factory() as db:
        for index, app in enumerate(apps):
            request_id = f'request-{index}'
            db.add(RequestRecord(request_id=request_id, tenant_id=app['tenant_id'], model='gpt-4o-mini',
                messages_json=[], prompt_text=f'private prompt {index}', prompt_hash=str(index)*64))
            db.add(CacheEvent(request_id=request_id, tenant_id=app['tenant_id'], model='gpt-4o-mini',
                cache_status=CacheStatus.MISS, threshold_used=.9, latency_ms=10))
        db.commit()
    for index in [0, 1]:
        headers = {**alice, 'X-Project-ID': apps[index]['project_id']}
        response = client.get('/api/v1/metrics/requests', headers=headers, params={'tenant_id': apps[2]['tenant_id']})
        assert response.status_code == 200, response.text
        assert response.json()['total'] == 1
        assert response.json()['items'][0]['prompt'] == f'private prompt {index}'
        dashboard = client.get('/api/v1/metrics/dashboard', headers=headers)
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()['summary']['total_requests'] == 1
    assert client.get('/api/v1/metrics/requests', headers={**alice, 'X-Project-ID': apps[2]['project_id']}).status_code == 404


def test_account_integration_settings_require_login_and_hide_secrets(account_app, monkeypatch):
    client, _ = account_app
    monkeypatch.setattr(auth.settings, 'DEFAULT_MODEL', 'claude-sonnet-5-5')
    monkeypatch.setattr(auth.settings, 'ANTHROPIC_API_KEY', 'private-provider-secret')
    monkeypatch.setattr(auth.settings, 'OPENAI_API_KEY', '')
    monkeypatch.setattr(auth.settings, 'ADDITIONAL_MODELS', [])
    assert client.get('/api/v1/account/integration').status_code == 401
    owner = register(client, 'alice@example.com')
    response = client.get('/api/v1/account/integration', headers=owner)
    assert response.status_code == 200
    assert response.json() == {
        'default_model': 'claude-sonnet-5-5', 'default_provider': 'anthropic',
        'configured': True, 'available_models': ['claude-sonnet-5-5'],
    }
    assert 'private-provider-secret' not in response.text


def create_workspace(client, name='My bot'):
    response = client.post('/api/v1/workspaces', json={'name': name})
    assert response.status_code == 201, response.text
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()
    return data, {'Authorization': 'Bearer ' + data['api_key']}


def test_workspaces_create_without_accounts_and_use_keys_for_identity(account_app):
    client, factory = account_app
    alice, alice_headers = create_workspace(client, 'Same label')
    bob, bob_headers = create_workspace(client, 'Same label')
    assert alice['project_id'] != bob['project_id']
    assert alice['tenant_id'] != bob['tenant_id']
    assert alice['api_key'] != bob['api_key']
    with factory() as db:
        assert db.query(User).count() == 0
        assert db.query(UserSession).count() == 0
        assert authenticate_project_key(db, alice['api_key']).tenant_id == alice['tenant_id']
        assert all(key.key_hash != alice['api_key'] for key in db.query(ProjectAPIKey))
    current = client.get('/api/v1/workspaces/current', headers=alice_headers, params={'project_id': bob['project_id']})
    assert current.status_code == 200
    assert current.json()['id'] == alice['project_id']
    assert 'api_key' not in current.json()
    keys = client.get('/api/v1/workspaces/current/keys', headers=alice_headers).json()
    assert len(keys) == 1 and keys[0]['project_id'] == alice['project_id']
    assert 'api_key' not in keys[0] and 'key_hash' not in keys[0]
    assert client.delete('/api/v1/workspaces/current/keys/' + bob['api_key_id'], headers=alice_headers).status_code == 404
    assert client.get('/application-scope', headers=alice_headers).json()['tenant_id'] == alice['tenant_id']
    assert client.get('/api/v1/projects', headers=alice_headers).status_code == 403
    assert client.get('/api/v1/workspaces/current', headers=bob_headers).json()['id'] == bob['project_id']


def test_workspace_rotation_and_current_key_lockout_protection(account_app):
    client, _ = account_app
    original, headers = create_workspace(client)
    path = '/api/v1/workspaces/current/keys'
    assert client.delete(path + '/' + original['api_key_id'], headers=headers).status_code == 409
    response = client.post(path, headers=headers, json={'name': 'replacement'})
    assert response.status_code == 201
    replacement = response.json()
    new_headers = {'Authorization': 'Bearer ' + replacement['api_key']}
    assert client.get('/api/v1/workspaces/current', headers=new_headers).json()['id'] == original['project_id']
    assert client.delete(path + '/' + original['api_key_id'], headers=new_headers).status_code == 204
    assert client.get('/api/v1/workspaces/current', headers=headers).status_code == 401
    assert client.get('/application-scope', headers=headers).status_code == 401
    assert client.get('/application-scope', headers=new_headers).status_code == 200


def test_workspace_identity_rejects_admin_metrics_missing_and_invalid_keys_even_in_dev(account_app, monkeypatch):
    client, _ = account_app
    monkeypatch.setattr(auth.settings, 'REQUIRE_API_KEY', False)
    for key in ['', 'wrong-key', 'admin-secret', 'dc_session_invalid']:
        headers = {'Authorization': 'Bearer ' + key} if key else {}
        for path in ['/current', '/current/keys', '/integration']:
            assert client.get('/api/v1/workspaces' + path, headers=headers).status_code == 401
        assert client.post('/api/v1/workspaces/current/keys', headers=headers, json={'name': 'bad'}).status_code == 401


def test_workspace_metrics_ignore_other_tenant_and_integration_hides_provider_secret(account_app, monkeypatch):
    client, factory = account_app
    alice, headers = create_workspace(client)
    bob, _ = create_workspace(client)
    monkeypatch.setattr(auth.settings, 'DEFAULT_MODEL', 'claude-sonnet-5-5')
    monkeypatch.setattr(auth.settings, 'ANTHROPIC_API_KEY', 'private-provider-secret')
    with factory() as db:
        for index, workspace in enumerate([alice, bob]):
            db.add(RequestRecord(request_id=f'r-{index}', tenant_id=workspace['tenant_id'], model='claude-test', messages_json=[], prompt_text=f'private-{index}', prompt_hash=str(index)*64))
            db.add(CacheEvent(request_id=f'r-{index}', tenant_id=workspace['tenant_id'], model='claude-test', cache_status=CacheStatus.MISS, threshold_used=.9, latency_ms=10))
        db.commit()
    result = client.get('/api/v1/metrics/requests', headers=headers, params={'tenant_id': bob['tenant_id']})
    assert result.status_code == 200
    assert result.json()['total'] == 1
    assert result.json()['items'][0]['prompt'] == 'private-0'
    response = client.get('/api/v1/workspaces/integration', headers=headers)
    assert response.json()['default_model'] == 'claude-sonnet-5-5'
    assert 'private-provider-secret' not in response.text


def test_workspace_create_validates_labels_and_throttles(account_app):
    client, factory = account_app
    assert client.post('/api/v1/workspaces', json={'name': '  '}).status_code == 422
    workspace, _ = create_workspace(client, '  My bot  ')
    assert workspace['project_name'] == 'My bot'
    with factory() as db:
        attempt = db.query(AuthAttempt).one()
        db.add_all([AuthAttempt(client_hash=attempt.client_hash, created_at=datetime.now(timezone.utc)) for _ in range(19)])
        db.commit()
    assert client.post('/api/v1/workspaces', json={'name': 'Another bot'}).status_code == 429
