"""Run only against a dedicated PostgreSQL test database (tables are cleared)."""
from backend.tests.conftest import seed_code
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
    source, destination = seed_code(source), seed_code(destination)
    return client.post('/api/transfers', json=dict(source_account_code=source, destination_account_code=destination, amount=amount, effective_date='2026-10-12'))

def test_actual_funds_path_and_reversal(client):
    response = client.post('/api/accounts', json={'name': '测试资金端点', 'kind': 'public'})
    assert response.status_code == 201
    extra = response.json()['code']
    import re
    assert re.fullmatch(r'FA-\d{4,}',extra)
    assert transfer(client, seed_code('opening'), seed_code('fund_pool'), '2000').status_code == 201
    assert transfer(client, seed_code('fund_pool'), extra, '300').status_code == 201
    expense = transfer(client, extra, seed_code('expense'), '50').json()
    summary = client.get('/api/funds/summary').json()
    assert {a['code']: a['balance_minor'] for a in summary['accounts']} == {seed_code('fund_pool'): 170000, extra: 25000}
    assert summary['total_minor'] == 195000
    assert sum(l['debit_minor'] - l['credit_minor'] for l in expense['journal_lines']) == 0
    reversal = client.post(f"/api/transfers/{expense['code']}/reverse", json={'reason': '重复登记'}).json()
    assert reversal['status'] == 'posted'
    assert client.get('/api/funds/summary').json()['total_minor'] == 200000
    assert client.get(f"/api/transfers/{expense['code']}").json()['status'] == 'reversed'

def test_pending_approval_and_roles(client):
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = transfer(client, seed_code('opening'), seed_code('fund_pool'), '100').json()
    assert pending['status'] == 'pending' and pending['journal_lines'] == []
    before = {a['code']: a for a in client.get('/api/accounts').json()}
    assert before[seed_code('fund_pool')]['last_posted_at'] is None
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    assert client.post('/api/accounts', json={'name': '禁止', 'kind': 'public'}).status_code == 403
    assert client.patch('/api/users/trusted', json={'role': 'admin'}).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f"/api/transfers/{pending['code']}/approve", json={'expected_version': pending['version']}).status_code == 200
    assert client.get('/api/funds/summary').json()['total_minor'] == 10000
    after = {a['code']: a for a in client.get('/api/accounts').json()}
    assert after[seed_code('fund_pool')]['last_posted_at'] is not None
    assert after[seed_code('opening')]['last_posted_at'] == after[seed_code('fund_pool')]['last_posted_at']
    assert client.post(f"/api/transfers/{pending['code']}/approve", json={'expected_version': pending['version']}).status_code == 409

def test_amount_precision(client):
    assert transfer(client, seed_code('opening'), seed_code('fund_pool'), '1.001').status_code == 400

def test_formal_write_failure_rolls_back(client):
    # A real PostgreSQL trigger induces failure after the transfer has been inserted.
    with engine.begin() as db:
        db.execute(text("CREATE OR REPLACE FUNCTION fail_journal() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'induced journal failure'; END $$"))
        db.execute(text('CREATE TRIGGER fail_journal BEFORE INSERT ON journal_lines FOR EACH ROW EXECUTE FUNCTION fail_journal()'))
    try:
        with pytest.raises(Exception, match='induced journal failure'):
            transfer(client, seed_code('opening'), seed_code('fund_pool'), '100')
        assert client.get('/api/transfers').json()['items'] == []
        assert client.get('/api/funds/summary').json()['total_minor'] == 0
        with engine.connect() as db:
            assert db.scalar(text('SELECT count(*) FROM audit_events')) == 0
            assert db.scalar(text('SELECT count(*) FROM journal_lines')) == 0
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_journal ON journal_lines'))
            db.execute(text('DROP FUNCTION fail_journal()'))


def test_fund_stocktake_transfers_and_reversal(client, monkeypatch):
    from backend.application import stocktakes
    monkeypatch.setattr(stocktakes, 'ENABLED', True)
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.post('/api/fund-stocktakes', json={'name': '期末核对'}).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    response = client.post('/api/fund-stocktakes', json={'name': '期末核对'})
    assert response.status_code == 201
    item = response.json()
    path = f"/api/fund-stocktakes/{item['id']}"
    accounts = {a['code']: a for a in client.get('/api/accounts').json()}
    assert accounts[seed_code('fund_pool')]['stocktake'] is None
    for endpoint in ('gain_account_code', 'loss_account_code'):
        assert accounts[item[endpoint]]['stocktake'] == {'id': item['id'], 'name': item['name'], 'status': 'in_progress'}
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    gain = transfer(client, item['gain_account_code'], seed_code('fund_pool'), '100').json()
    loss = transfer(client, seed_code('fund_pool'), item['loss_account_code'], '20').json()
    assert client.get('/api/funds/summary').json()['total_minor'] == 8000
    assert {t['code'] for t in client.get(path).json()['transfers']} == {gain['code'], loss['code']}
    reversal = client.post(f"/api/transfers/{loss['code']}/reverse", json={'reason': '盘亏登记有误'}).json()
    assert client.get('/api/funds/summary').json()['total_minor'] == 10000
    detail = client.get(path).json()
    assert {t['code'] for t in detail['transfers']} == {gain['code'], loss['code'], reversal['code']}
    assert next(t for t in detail['transfers'] if t['code'] == loss['code'])['status'] == 'reversed'
    assert client.post(path + '/end').json()['status'] == 'ended'
    assert client.post(path + '/end').json()['status'] == 'ended'
    accounts = {a['code']: a for a in client.get('/api/accounts').json()}
    assert all(accounts[item[key]]['stocktake']['status'] == 'ended' for key in ('gain_account_code', 'loss_account_code'))
    assert client.patch(path, json={'description': '已核对凭证'}).json()['description'] == '已核对凭证'
    assert client.get('/api/funds/summary').json()['total_minor'] == 10000
    assert [s['id'] for s in client.get('/api/fund-stocktakes?status=ended').json()['items']] == [item['id']]


def test_fund_stocktake_endpoint_failure_rolls_back(client, monkeypatch):
    from backend.application import stocktakes
    monkeypatch.setattr(stocktakes, 'ENABLED', True)
    with engine.begin() as db:
        db.execute(text("CREATE OR REPLACE FUNCTION fail_stocktake_endpoint() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.name = '失败核对（资金盘亏）' THEN RAISE EXCEPTION 'induced endpoint failure'; END IF; RETURN NEW; END $$"))
        db.execute(text('CREATE TRIGGER fail_stocktake_endpoint BEFORE INSERT ON fund_accounts FOR EACH ROW EXECUTE FUNCTION fail_stocktake_endpoint()'))
    try:
        with pytest.raises(Exception, match='induced endpoint failure'):
            client.post('/api/fund-stocktakes', json={'name': '失败核对'})
        assert client.get('/api/fund-stocktakes').json()['items'] == []
        accounts = client.get('/api/accounts').json()
        assert not any(a['name'].startswith('失败核对') for a in accounts)
        assert all(a['stocktake'] is None for a in accounts)
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_stocktake_endpoint ON fund_accounts'))
            db.execute(text('DROP FUNCTION fail_stocktake_endpoint()'))


def test_account_contact_type_tags_and_disabled_processing(client):
    member=client.post('/api/members',json={'name':'小王'}).json()
    account=client.post('/api/accounts',json={'name':'展会私账','kind':'private','member_code':member['code'],'tags':[' 印刷 ','印刷','','自定义'],'avatar_url':'https://example.test/avatar.png'}).json()
    assert account['tags']==['印刷','自定义']
    assert client.patch(f"/api/accounts/{account['code']}",json={'kind':'public'}).status_code==422
    assert client.patch(f"/api/members/{member['code']}",json={'name':'王同学'}).status_code==200
    assert next(a for a in client.get('/api/accounts').json() if a['code']==account['code'])['name']=='展会私账'
    cleared=client.patch(f"/api/accounts/{account['code']}",json={'member_code':None,'avatar_url':None}).json()
    assert cleared['member_code'] is None and cleared['avatar_url'] is None
    assert [a['code'] for a in client.get('/api/accounts?tag=自定义').json()]==[account['code']]
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending=transfer(client,account['code'],seed_code('expense'),'300').json()
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert client.patch(f"/api/accounts/{account['code']}",json={'active':False}).status_code==200
    assert client.post(f"/api/transfers/{pending['code']}/approve",json={'expected_version':pending['version']}).status_code==200
    assert transfer(client,account['code'],seed_code('expense'),'1').status_code==409
    assert client.post(f"/api/transfers/{pending['code']}/reverse",json={'reason':'录错'}).status_code==201


def test_list_pagination_filters_and_health(client):
    for amount in ('100', '200', '300'):
        assert transfer(client, seed_code('opening'), seed_code('fund_pool'), amount).status_code == 201
    page = client.get('/api/transfers', params={'page': 2, 'limit': 2}).json()
    assert page['total'] == 3 and page['page'] == 2 and page['limit'] == 2
    assert len(page['items']) == 1
    filtered = client.get('/api/transfers', params={'q': '资金池', 'date_from': '2026-10-11', 'date_to': '2026-10-13'}).json()
    assert filtered['total'] == 3
    client.post('/api/transfers', json=dict(source_account_code=seed_code('opening'), destination_account_code=seed_code('fund_pool'),
                                            amount='50', effective_date='2026-10-12', description='交通', tags=['差旅']))
    assert client.get('/api/transfers', params={'q': '差旅'}).json()['total'] == 1
    first = client.get('/api/transfers').json()['items'][0]
    import re
    assert re.fullmatch(r'FT-\d{6,}',first['code'])
    assert client.get('/api/transfers',params={'q':first['code']}).json()['total'] == 1
    health = client.get('/api/health').json()
    assert health['status'] == 'ok'
    assert health['schema_revision'] == '0001'
    assert 'version' in health and 'git_sha' in health
