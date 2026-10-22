import os
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}
DEFAULT_SESSION_TTL_HOURS = 168


@dataclass(frozen=True)
class CasdoorConfig:
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str
    initial_admin_subject: str
    initial_admin_name: str | None


def auth_mode():
    mode = os.getenv('AUTH_MODE', '')
    if mode not in ('development', 'casdoor'):
        raise RuntimeError('AUTH_MODE must be explicitly set to development or casdoor')
    return mode


def session_ttl():
    raw = os.getenv('SESSION_TTL_HOURS', str(DEFAULT_SESSION_TTL_HOURS))
    try:
        hours = int(raw)
    except ValueError:
        raise RuntimeError('SESSION_TTL_HOURS must be a positive integer') from None
    if hours <= 0:
        raise RuntimeError('SESSION_TTL_HOURS must be a positive integer')
    return timedelta(hours=hours)


def cookie_secure():
    return os.getenv('COOKIE_SECURE', 'false').lower() == 'true'


def _required(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f'Missing required configuration: {name}')
    return value


def _https_url(name, value):
    parsed = urlparse(value)
    if not parsed.netloc or (parsed.scheme != 'https' and parsed.hostname not in LOOPBACK_HOSTS):
        raise RuntimeError(f'{name} must be an https URL (http is allowed only for loopback testing)')


def casdoor_config():
    values = {name: _required(name) for name in (
        'CASDOOR_ISSUER', 'CASDOOR_CLIENT_ID', 'CASDOOR_CLIENT_SECRET',
        'CASDOOR_REDIRECT_URI', 'INITIAL_ADMIN_SUBJECT')}
    issuer = values['CASDOOR_ISSUER'].rstrip('/')
    _https_url('CASDOOR_ISSUER', issuer)
    _https_url('CASDOOR_REDIRECT_URI', values['CASDOOR_REDIRECT_URI'])
    return CasdoorConfig(
        issuer=issuer,
        client_id=values['CASDOOR_CLIENT_ID'],
        client_secret=values['CASDOOR_CLIENT_SECRET'],
        redirect_uri=values['CASDOOR_REDIRECT_URI'],
        scope=os.getenv('CASDOOR_SCOPE', '').strip() or 'openid profile email',
        initial_admin_subject=values['INITIAL_ADMIN_SUBJECT'],
        initial_admin_name=os.getenv('INITIAL_ADMIN_NAME', '').strip() or None,
    )


def validate_auth_config():
    mode = auth_mode()
    session_ttl()
    cookie_secure()
    if mode == 'casdoor':
        casdoor_config()
    return mode
