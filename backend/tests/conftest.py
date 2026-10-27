import os
os.environ['AUTH_MODE'] = 'development'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.infrastructure.database import engine
from backend.infrastructure.models import Base
from backend.application.initialize import initialize
from backend.entrypoints.http import create_app

CASDOOR_ENV = {
    'AUTH_MODE': 'casdoor',
    'CASDOOR_ISSUER': 'https://idp.example',
    'CASDOOR_CLIENT_ID': 'fgas-test-client',
    'CASDOOR_CLIENT_SECRET': 'fgas-test-secret',
    'CASDOOR_REDIRECT_URI': 'https://fgas.example/api/auth/casdoor/callback',
    'INITIAL_ADMIN_SUBJECT': 'initial-admin',
    'INITIAL_ADMIN_NAME': '初始管理员',
    'SESSION_TTL_HOURS': '168',
    'COOKIE_SECURE': 'false',
}

def prepare_database():
    if not os.getenv('FGAS_TEST_DATABASE'): pytest.skip('Set FGAS_TEST_DATABASE=1 with dedicated DATABASE_URL')
    with engine.begin() as db:
        if db.scalar(text('SELECT current_database()')) != 'fgas_test':
            raise RuntimeError('Fixture requires dedicated fgas_test database')
        for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('AUTH_MODE', 'development')
    prepare_database()
    initialize()
    with TestClient(create_app()) as client:
        client.post('/api/auth/login', json={'user_id': 'trusted'})
        yield client

@pytest.fixture
def casdoor_client(monkeypatch):
    for name, value in CASDOOR_ENV.items(): monkeypatch.setenv(name, value)
    prepare_database()
    initialize()
    with TestClient(create_app()) as client:
        yield client


def seed_code(identifier):
    from backend.infrastructure.database import Session
    from backend.infrastructure.models import FundAccount, StockAccount
    if identifier not in {'fund_pool', 'opening', 'expense', 'income', 'main'}:
        return identifier
    with Session() as db:
        return db.get(StockAccount if identifier == 'main' else FundAccount, identifier).code
