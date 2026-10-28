"""Minimal Casdoor OIDC authorization-code client with PKCE and signed state."""
import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import httpx

from backend.infrastructure import auth_config, store
from backend.application import agent_access, web_agent
from backend.infrastructure.models import User
from backend.kernel.accounting import DomainError

STATE_COOKIE = 'fgas_sso_state'
STATE_MAX_AGE = 600
DISCOVERY_TTL = 300
LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}
_discovery_cache = {}
_discovery_lock = threading.Lock()


def _endpoint(value):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if not parsed.netloc or (parsed.scheme != 'https' and parsed.hostname not in LOOPBACK_HOSTS):
        return None
    return value


def discover():
    config = auth_config.casdoor_config()
    now = time.monotonic()
    cached = _discovery_cache.get(config.issuer)
    if cached and cached[0] > now:
        return cached[1]
    with _discovery_lock:
        cached = _discovery_cache.get(config.issuer)
        if cached and cached[0] > now:
            return cached[1]
        try:
            response = httpx.get(config.issuer + '/.well-known/openid-configuration', timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            raise DomainError('身份服务暂时不可用', 502) from None
        endpoints = {
            'issuer': payload.get('issuer', ''),
            'authorization_endpoint': _endpoint(payload.get('authorization_endpoint')),
            'token_endpoint': _endpoint(payload.get('token_endpoint')),
            'userinfo_endpoint': _endpoint(payload.get('userinfo_endpoint')),
        }
        if endpoints['issuer'].rstrip('/') != config.issuer or not all(
                endpoints[name] for name in ('authorization_endpoint', 'token_endpoint', 'userinfo_endpoint')):
            raise DomainError('身份服务配置无效', 502)
        _discovery_cache[config.issuer] = (now + DISCOVERY_TTL, endpoints)
        return endpoints


def _state_key(config):
    return hmac.new(config.client_secret.encode(), b'fgas-sso-state-v1', hashlib.sha256).digest()


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=')


def _b64decode(value):
    return base64.urlsafe_b64decode(value + b'=' * (-len(value) % 4))


def _state_cookie(state, verifier):
    config = auth_config.casdoor_config()
    payload = json.dumps({'state': state, 'verifier': verifier, 'exp': int(time.time()) + STATE_MAX_AGE},
                         separators=(',', ':')).encode()
    signature = hmac.new(_state_key(config), payload, hashlib.sha256).digest()
    return (_b64encode(payload) + b'.' + _b64encode(signature)).decode()


def _read_state(value):
    config = auth_config.casdoor_config()
    try:
        encoded, signature = value.encode().split(b'.', 1)
        payload = _b64decode(encoded)
        expected = hmac.new(_state_key(config), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature), expected):
            raise ValueError('signature')
        data = json.loads(payload)
        if not isinstance(data.get('state'), str) or not isinstance(data.get('verifier'), str) or not isinstance(data.get('exp'), int):
            raise ValueError('payload')
    except (AttributeError, ValueError, TypeError, KeyError):
        raise DomainError('登录状态已失效，请重新登录', 400) from None
    if data['exp'] < int(time.time()):
        raise DomainError('登录状态已失效，请重新登录', 400)
    return data


def begin():
    config = auth_config.casdoor_config()
    endpoints = discover()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64encode(hashlib.sha256(verifier.encode()).digest()).decode()
    query = urlencode({
        'response_type': 'code',
        'client_id': config.client_id,
        'redirect_uri': config.redirect_uri,
        'scope': config.scope,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
    })
    return f"{endpoints['authorization_endpoint']}?{query}", _state_cookie(state, verifier)


def exchange_code(endpoints, code, verifier):
    config = auth_config.casdoor_config()
    try:
        response = httpx.post(endpoints['token_endpoint'], data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': config.redirect_uri,
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'code_verifier': verifier,
        }, timeout=10)
        response.raise_for_status()
        token = response.json().get('access_token')
    except Exception:
        raise DomainError('登录失败，请重试', 502) from None
    if not isinstance(token, str) or not token:
        raise DomainError('登录失败，请重试', 502)
    return token


def fetch_userinfo(endpoints, access_token):
    try:
        response = httpx.get(endpoints['userinfo_endpoint'],
                             headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
        response.raise_for_status()
        profile = response.json()
    except Exception:
        raise DomainError('登录失败，请重试', 502) from None
    if not isinstance(profile, dict) or not isinstance(profile.get('sub'), str) or not profile['sub'].strip():
        raise DomainError('身份服务返回的用户标识无效', 502)
    return profile


def finish(code, state, cookie_value):
    if not code or not state or not cookie_value:
        raise DomainError('登录状态已失效，请重新登录', 400)
    pending = _read_state(cookie_value)
    if not hmac.compare_digest(pending['state'], state):
        raise DomainError('登录状态已失效，请重新登录', 400)
    endpoints = discover()
    access_token = exchange_code(endpoints, code, pending['verifier'])
    return fetch_userinfo(endpoints, access_token)


def _text(profile, *keys):
    for key in keys:
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def provision(db, profile):
    config = auth_config.casdoor_config()
    subject = profile['sub'].strip()
    username = _text(profile, 'preferred_username', 'name')
    email = _text(profile, 'email')
    display_name = _text(profile, 'displayName', 'name', 'preferred_username') or email \
        or config.initial_admin_name or subject
    now = datetime.now(timezone.utc)
    store.lock(db)
    user = store.user_by_sso_subject(db, subject)
    if user:
        if not user.active:
            raise DomainError('账号已停用，请联系管理员', 403)
        user.display_name = display_name
        user.sso_username = username
        user.email = email
        user.last_login_at = now
        db.flush()
        return user
    identity_names = {value for value in (username, _text(profile, 'name')) if value}
    user = User(
        display_name=display_name,
        role='admin' if config.initial_admin_subject == subject or config.initial_admin_subject in identity_names else 'untrusted',
        active=True,
        sso_subject=subject,
        sso_username=username,
        email=email,
        last_login_at=now,
    )
    db.add(user)
    db.flush()
    if web_agent.enabled():
        agent_access.create_credential(db, user, {'name': '网页助手', 'level': 'low'})
    return user
