"""Human authentication; Casdoor flows use a mocked identity provider."""
import asyncio
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import func, select

from backend.application import sso
from backend.infrastructure import store
from backend.infrastructure.database import Session
from backend.infrastructure.models import LoginSession, User

ENDPOINTS = {
    'issuer': 'https://idp.example',
    'authorization_endpoint': 'https://idp.example/authorize',
    'token_endpoint': 'https://idp.example/token',
    'userinfo_endpoint': 'https://idp.example/userinfo',
}


@pytest.fixture
def idp(monkeypatch):
    profile = {'sub': 'uid-alice', 'name': 'alice', 'email': 'alice@example.com'}
    monkeypatch.setattr(sso, 'discover', lambda: dict(ENDPOINTS))
    monkeypatch.setattr(sso, 'exchange_code', lambda endpoints, code, verifier: 'access-token')
    monkeypatch.setattr(sso, 'fetch_userinfo', lambda endpoints, token: dict(profile))
    return profile


def begin_login(client):
    response = client.get('/api/auth/casdoor/login', follow_redirects=False)
    assert response.status_code == 303
    return parse_qs(urlparse(response.headers['location']).query)


def callback(client, state, code='valid-code'):
    return client.get('/api/auth/casdoor/callback', params={'code': code, 'state': state}, follow_redirects=False)


def login(client):
    query = begin_login(client)
    return callback(client, query['state'][0])


def use_session(client, token):
    client.cookies.clear()
    client.cookies.set('fgas_session', token)


def user_by_subject(subject):
    with Session() as db:
        return db.scalar(select(User).where(User.sso_subject == subject))


def session_count(user_id):
    with Session() as db:
        return db.scalar(select(func.count()).select_from(LoginSession).where(LoginSession.user_id == user_id))


def test_login_session_is_committed_before_response(client):
    visible_at_response = []

    async def observe_response(scope, receive, send):
        async def observe(message):
            if scope['path'] == '/api/auth/login' and message['type'] == 'http.response.start':
                cookie = SimpleCookie()
                for name, value in message['headers']:
                    if name.lower() == b'set-cookie':
                        cookie.load(value.decode())
                with Session() as db:
                    visible_at_response.append(db.get(LoginSession, cookie['fgas_session'].value) is not None)
            await send(message)
        await client.app(scope, receive, observe)

    async def login_and_read():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=observe_response), base_url='http://testserver') as http:
            response = await http.post('/api/auth/login', json={'user_id': 'untrusted'})
            assert response.status_code == 200
            assert (await http.get('/api/auth/me')).json()['id'] == 'untrusted'

    asyncio.run(login_and_read())
    assert visible_at_response == [True]


def test_login_redirect_contains_pkce_and_signed_state(casdoor_client, idp):
    response = casdoor_client.get('/api/auth/casdoor/login', follow_redirects=False)
    assert response.status_code == 303
    parsed = urlparse(response.headers['location'])
    assert parsed.netloc == 'idp.example'
    query = parse_qs(parsed.query)
    assert query['response_type'] == ['code']
    assert query['client_id'] == ['fgas-test-client']
    assert query['redirect_uri'] == ['https://fgas.example/api/auth/casdoor/callback']
    assert query['code_challenge_method'] == ['S256']
    pending = sso._read_state(casdoor_client.cookies.get('fgas_sso_state'))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).rstrip(b'=').decode()
    assert challenge == query['code_challenge'][0]
    assert pending['state'] == query['state'][0]


def test_first_login_provisions_an_untrusted_user(casdoor_client, idp, monkeypatch):
    monkeypatch.setenv('FGAS_WEB_AGENT_PROTOTYPE', '1')
    response = login(casdoor_client)
    assert response.status_code == 303 and response.headers['location'] == '/'
    assert any('fgas_session=' in value and 'Max-Age=604800' in value
               for value in response.headers.get_list('set-cookie'))
    assert casdoor_client.get('/api/auth/me').json() == {
        'id': user_by_subject('uid-alice').id, 'display_name': 'alice', 'role': 'untrusted', 'active': True}
    user = user_by_subject('uid-alice')
    assert user.sso_username == 'alice' and user.email == 'alice@example.com'
    assert user.last_login_at is not None and user.created_at is not None
    connections = casdoor_client.get('/api/agent-credentials').json()
    assert len(connections) == 1
    assert (connections[0]['owner_user_id'], connections[0]['level'], connections[0]['active']) == (user.id, 'low', True)
    login(casdoor_client)
    assert len(casdoor_client.get('/api/agent-credentials').json()) == 1


def test_initial_admin_matches_subject_once(casdoor_client, idp, monkeypatch):
    monkeypatch.setenv('INITIAL_ADMIN_SUBJECT', 'uid-root')
    idp.update(sub='uid-root', name='root')
    login(casdoor_client)
    assert casdoor_client.get('/api/auth/me').json()['role'] == 'admin'
    with Session.begin() as db:
        db.scalar(select(User).where(User.sso_subject == 'uid-root')).role = 'untrusted'
    login(casdoor_client)
    assert casdoor_client.get('/api/auth/me').json()['role'] == 'untrusted'


def test_initial_admin_matches_username_on_first_provision(casdoor_client, idp, monkeypatch):
    monkeypatch.setenv('INITIAL_ADMIN_SUBJECT', 'boss')
    idp.update(sub='uid-boss', name='boss')
    login(casdoor_client)
    assert casdoor_client.get('/api/auth/me').json()['role'] == 'admin'
    assert user_by_subject('uid-boss').role == 'admin'


def test_disabled_user_login_is_rejected_without_session(casdoor_client, idp):
    login(casdoor_client)
    user = user_by_subject('uid-alice')
    with Session.begin() as db:
        db.get(User, user.id).active = False
    assert casdoor_client.get('/api/auth/me').status_code == 401
    response = login(casdoor_client)
    assert response.headers['location'] == '/?sso_error=user_disabled'
    assert session_count(user.id) == 1


def test_invalid_or_missing_state_is_rejected(casdoor_client, idp):
    query = begin_login(casdoor_client)
    response = callback(casdoor_client, query['state'][0] + 'tampered')
    assert response.status_code == 303
    assert response.headers['location'] == '/?sso_error=invalid_state'
    assert casdoor_client.get('/api/auth/me').status_code == 401

    query = begin_login(casdoor_client)
    casdoor_client.cookies.clear()
    response = callback(casdoor_client, query['state'][0])
    assert response.headers['location'] == '/?sso_error=invalid_state'


def test_provider_denial_is_reported(casdoor_client, idp):
    response = casdoor_client.get('/api/auth/casdoor/callback', params={'error': 'access_denied'},
                                  follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/?sso_error=access_denied'


def test_casdoor_mode_rejects_development_login(casdoor_client):
    assert casdoor_client.get('/api/auth/config').json() == {'mode': 'casdoor', 'web_agent_prototype': False}
    assert casdoor_client.get('/api/auth/users').status_code == 404
    assert casdoor_client.post('/api/auth/login', json={'user_id': 'admin'}).status_code == 404


def test_development_mode_rejects_casdoor_routes(client):
    assert client.get('/api/auth/config').json() == {'mode': 'development', 'web_agent_prototype': False}
    assert client.get('/api/auth/casdoor/login', follow_redirects=False).status_code == 404
    assert client.get('/api/auth/casdoor/callback', follow_redirects=False).status_code == 404


def test_expired_session_is_rejected(client):
    token = client.cookies.get('fgas_session')
    with Session.begin() as db:
        db.get(LoginSession, token).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert client.get('/api/auth/me').status_code == 401


def test_force_logout_revokes_sessions_and_flags_self(client):
    client.post('/api/auth/login', json={'user_id': 'admin'})
    admin_token = client.cookies.get('fgas_session')
    with Session.begin() as db:
        trusted_id = store.get_user(db, 'trusted').id
        store.delete_sessions_for_user(db, trusted_id)
        trusted_token = store.create_session(db, trusted_id)
    response = client.post(f'/api/users/{trusted_id}/logout')
    assert response.json() == {'ok': True, 'revoked': 1, 'self': False}
    use_session(client, trusted_token)
    assert client.get('/api/auth/me').status_code == 401

    use_session(client, admin_token)
    me = client.get('/api/auth/me').json()
    response = client.post(f"/api/users/{me['id']}/logout")
    assert response.json()['self'] is True
    assert any('Max-Age=0' in value for value in response.headers.get_list('set-cookie'))
    use_session(client, admin_token)
    assert client.get('/api/auth/me').status_code == 401


def test_last_active_admin_is_protected(client):
    client.post('/api/auth/login', json={'user_id': 'admin'})
    me = client.get('/api/auth/me').json()
    assert client.patch(f"/api/users/{me['id']}", json={'role': 'trusted'}).status_code == 409
    assert client.patch(f"/api/users/{me['id']}", json={'active': False}).status_code == 409
    assert client.patch('/api/users/trusted', json={'role': 'admin'}).status_code == 200
    assert client.patch(f"/api/users/{me['id']}", json={'role': 'trusted'}).status_code == 200


def test_deactivation_revokes_user_sessions(client):
    client.post('/api/auth/login', json={'user_id': 'admin'})
    with Session.begin() as db:
        trusted_id = store.get_user(db, 'trusted').id
        store.delete_sessions_for_user(db, trusted_id)
        token = store.create_session(db, trusted_id)
    assert client.patch(f'/api/users/{trusted_id}', json={'active': False}).status_code == 200
    use_session(client, token)
    assert client.get('/api/auth/me').status_code == 401
    assert session_count(trusted_id) == 0
