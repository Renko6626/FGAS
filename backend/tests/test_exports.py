"""CSV ledger behavior through authenticated HTTP and the real test database."""
import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from zipfile import ZipFile

from backend.tests.conftest import seed_code
from backend.tests.test_funds import transfer


def exported(client, mode, **params):
    response = client.get('/api/exports', params=dict(mode=mode, **params))
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    with ZipFile(BytesIO(response.content)) as archive:
        result = {}
        for name in archive.namelist():
            data = archive.read(name)
            if name.endswith('.csv'):
                assert data.startswith(b'\xef\xbb\xbf')
                result[name] = list(csv.DictReader(StringIO(data.decode('utf-8-sig'))))
        assert '实际入账' in archive.read('说明.txt').decode('utf-8-sig')
        return result


def test_export_funds_snapshot_changes_reversal_and_csv(client):
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = transfer(client, 'opening', 'fund_pool', '7.25').json()
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    text = '=SUM(1,2)\n"用途"'
    first = client.post('/api/transfers', json=dict(
        source_account_code=seed_code('opening'), destination_account_code=seed_code('fund_pool'),
        amount='100.00', effective_date='2026-01-01', description=text)).json()
    t = first['posted_at']
    before = exported(client, 'snapshot', as_of=t)['资金余额.csv']
    approved = client.post(f"/api/transfers/{pending['code']}/approve", json={'expected_version': pending['version']})
    assert approved.status_code == 200
    reverse = client.post(f"/api/transfers/{first['code']}/reverse", json={'reason': '更正'}).json()
    u = reverse['posted_at']
    # Later posting must not enter the explicitly closed interval.
    transfer(client, 'opening', 'fund_pool', '3.00')
    changes = exported(client, 'changes', start=t, end=u)['资金台账.csv']
    assert {r['资金单编号'] for r in changes} == {pending['code'], reverse['code']}
    assert next(r for r in changes if r['资金单编号'] == reverse['code'])['冲销原单编号'] == first['code']
    after = exported(client, 'snapshot', as_of=u)['资金余额.csv']
    balances = {r['账户编号']: Decimal(r['余额（元）']) for r in before}
    for row in changes:
        balances[row['来源账户编号']] -= Decimal(row['金额（元）'])
        balances[row['去向账户编号']] += Decimal(row['金额（元）'])
    assert balances == {r['账户编号']: Decimal(r['余额（元）']) for r in after}
    assert balances[seed_code('fund_pool')] == Decimal('7.25')
    assert balances[seed_code('opening')] == Decimal('-7.25')
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    still_pending = transfer(client, 'opening', 'fund_pool', '9.00').json()
    all_rows = exported(client, 'all')['资金台账.csv']
    original = next(r for r in all_rows if r['资金单编号'] == first['code'])
    assert original['用途'] == "'" + text and original['当前状态'] == '已冲销'
    assert next(r for r in all_rows if r['资金单编号'] == still_pending['code'])['实际入账时间'] == ''
    # Include original posted entries even if their current state is reversed.
    all_changes = exported(client, 'changes', start='2020-01-01T00:00:00+08:00')['资金台账.csv']
    assert first['code'] in {r['资金单编号'] for r in all_changes}
    assert still_pending['code'] not in {r['资金单编号'] for r in all_changes}


def test_export_stock_snapshot_and_later_completion(client):
    supplier = client.post('/api/stock-accounts', json={'name': '商家', 'kind': 'external'}).json()['code']
    main = seed_code('main')
    second = client.post('/api/stock-accounts', json={'name': '另一仓', 'kind': 'internal'}).json()['code']
    for code in ('BOOK-1', 'BOOK-2'):
        assert client.post('/api/skus', json={'code': code, 'name': '书,"版本"\n说明', 'unit': '本'}).status_code == 201
    incoming = client.post('/api/stock-transfers', json=dict(source_account_code=supplier,
        destination_account_code=main, effective_date='2026-01-01', lines=[
            {'sku_code': 'BOOK-1', 'quantity': '10'}, {'sku_code': 'BOOK-2', 'quantity': '4'}])).json()
    t = datetime.now(timezone.utc).isoformat()
    before = exported(client, 'snapshot', as_of=t)['仓库库存.csv']
    assert all(r['数量'] == '0' for r in before)
    assert client.post(f"/api/stock-transfers/{incoming['code']}/completion",
                       json={'effective_date': '2026-01-02'}).status_code == 200
    moved = client.post('/api/stock-transfers', json=dict(source_account_code=main,
        destination_account_code=second, effective_date='2026-01-03',
        lines=[{'sku_code': 'BOOK-1', 'quantity': '3'}])).json()
    assert client.post(f"/api/stock-transfers/{moved['code']}/completion",
                       json={'effective_date': '2026-01-03'}).status_code == 200
    u = datetime.now(timezone.utc).isoformat()
    assert client.patch(f'/api/stock-accounts/{second}', json={'active': False}).status_code == 200
    changes = exported(client, 'changes', start=t, end=u)['货物台账.csv']
    assert len(changes) == 3
    assert all(r['完成报告编号'].startswith('SC-') for r in changes)
    quantities = {(r['仓库编号'], r['SKU']): int(r['数量']) for r in before}
    for r in changes:
        for side, sign in [('来源', -1), ('去向', 1)]:
            key = (r[f'{side}账户编号'], r['SKU'])
            if key in quantities:
                quantities[key] += sign * int(r['数量'])
    after = exported(client, 'snapshot', as_of=u)['仓库库存.csv']
    assert quantities == {(r['仓库编号'], r['SKU']): int(r['数量']) for r in after}
    assert quantities[(main, 'BOOK-1')] == 7 and quantities[(second, 'BOOK-1')] == 3
    assert any(r['仓库编号'] == second and r['当前启用'] == '否' for r in after)
    all_rows = exported(client, 'all')['货物台账.csv']
    assert len(all_rows) == 3 and all_rows[0]['商品名称'] == '书,"版本"\n说明'


def test_export_empty_auth_and_time_validation(client):
    assert exported(client, 'all')['资金台账.csv'] == []
    for params in [dict(mode='changes'), dict(mode='snapshot', as_of='2026-01-01T00:00:00'),
                   dict(mode='all', start='2026-01-01T00:00:00Z'),
                   dict(mode='snapshot', as_of='2999-01-01T00:00:00Z'),
                   dict(mode='changes', start='2026-02-01T00:00:00Z', end='2026-01-01T00:00:00Z')]:
        assert client.get('/api/exports', params=params).status_code in (400, 422)
    client.cookies.clear()
    assert client.get('/api/exports', params={'mode': 'all'}).status_code == 401
