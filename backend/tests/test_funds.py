"""Run only against a dedicated PostgreSQL test database (tables are cleared)."""
import os
os.environ['AUTH_MODE'] = 'development'
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, event
from backend.infrastructure.database import engine, Session
from backend.infrastructure.models import Base, JournalLine
from backend.application.initialize import initialize
from backend.entrypoints.http import app

def transfer(client, source, destination, amount):
    return client.post('/api/transfers', json=dict(source_account_id=source, destination_account_id=destination, amount=amount, effective_date='2026-10-12'))

def test_actual_funds_path_and_reversal(client):
    response = client.post('/api/accounts', json={'name': '测试资金端点', 'kind': 'asset', 'is_fund': True})
    assert response.status_code == 201
    extra = response.json()['id']
    assert transfer(client, 'opening', 'fund_pool', '2000').status_code == 201
    assert transfer(client, 'fund_pool', extra, '300').status_code == 201
    expense = transfer(client, extra, 'expense', '50').json()
    summary = client.get('/api/funds/summary').json()
    assert {a['id']: a['balance_minor'] for a in summary['accounts']} == {'fund_pool': 170000, extra: 25000}
    assert summary['total_minor'] == 195000
    assert sum(l['debit_minor'] - l['credit_minor'] for l in expense['journal_lines']) == 0
    reversal = client.post(f"/api/transfers/{expense['id']}/reverse", json={'reason': '重复登记'}).json()
    assert reversal['status'] == 'posted'
    assert client.get('/api/funds/summary').json()['total_minor'] == 200000
    assert client.get(f"/api/transfers/{expense['id']}").json()['status'] == 'reversed'

def test_pending_approval_and_roles(client):
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = transfer(client, 'opening', 'fund_pool', '100').json()
    assert pending['status'] == 'pending' and pending['journal_lines'] == []
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    assert client.post('/api/accounts', json={'name': '禁止', 'kind': 'asset'}).status_code == 403
    assert client.patch('/api/users/trusted', json={'role': 'admin'}).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f"/api/transfers/{pending['id']}/approve", json={'expected_version': pending['version']}).status_code == 200
    assert client.get('/api/funds/summary').json()['total_minor'] == 10000
    assert client.post(f"/api/transfers/{pending['id']}/approve", json={'expected_version': pending['version']}).status_code == 409

def test_amount_precision(client):
    assert transfer(client, 'opening', 'fund_pool', '1.001').status_code == 400

def test_formal_write_failure_rolls_back(client):
    # A real PostgreSQL trigger induces failure after the transfer has been inserted.
    with engine.begin() as db:
        db.execute(text("CREATE OR REPLACE FUNCTION fail_journal() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'induced journal failure'; END $$"))
        db.execute(text('CREATE TRIGGER fail_journal BEFORE INSERT ON journal_lines FOR EACH ROW EXECUTE FUNCTION fail_journal()'))
    try:
        with pytest.raises(Exception, match='induced journal failure'):
            transfer(client, 'opening', 'fund_pool', '100')
        assert client.get('/api/transfers').json() == []
        assert client.get('/api/funds/summary').json()['total_minor'] == 0
        with engine.connect() as db:
            assert db.scalar(text('SELECT count(*) FROM audit_events')) == 0
            assert db.scalar(text('SELECT count(*) FROM journal_lines')) == 0
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_journal ON journal_lines'))
            db.execute(text('DROP FUNCTION fail_journal()'))
