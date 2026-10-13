import os
os.environ['AUTH_MODE'] = 'development'
import pytest
from fastapi.testclient import TestClient
from backend.infrastructure.database import engine
from backend.infrastructure.models import Base
from backend.application.initialize import initialize
from backend.entrypoints.http import app

@pytest.fixture
def client():
    if not os.getenv('FGAS_TEST_DATABASE'): pytest.skip('Set FGAS_TEST_DATABASE=1 with dedicated DATABASE_URL')
    with engine.begin() as db:
        for table in reversed(Base.metadata.sorted_tables): db.execute(table.delete())
    initialize()
    with TestClient(app) as client:
        client.post('/api/auth/login', json={'user_id': 'trusted'})
        yield client

