"""Real stock submission/approval paths; isolated PostgreSQL fixture only."""
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.entrypoints.http import create_app
from backend.infrastructure.database import Session
from backend.infrastructure.models import StockTransfer, StockTransferLine, JournalLine




def test_sku_thumbnail_url(client):
    image = 'https://example.com/book.png'
    response = client.post('/api/skus', json=dict(code=' bad-01-a ', name='博丽灵梦徽章 58mm哑光A款', unit='枚', tags=['类别:徽章', '角色:博丽灵梦'], avatar_url=image))
    assert response.status_code == 201
    item = response.json()
    assert item['code'] == 'BAD-01-A'
    assert client.post('/api/skus', json=dict(code='bad-01-a', name='另一商品', unit='个')).status_code == 409
    other = client.post('/api/skus', json=dict(code='ARC-01-A', name='博丽灵梦立牌 10cm A款', unit='个', tags=['类别:立牌', '角色:博丽灵梦'])).json()
    assert client.patch('/api/skus/ARC-01-A', json={'code': 'BAD-01-A'}).status_code == 409
    assert [s['code'] for s in client.get('/api/skus', params={'code': 'bad-01-a'}).json()] == ['BAD-01-A']
    assert [s['code'] for s in client.get('/api/skus', params={'tag': '类别:立牌'}).json()] == ['ARC-01-A']
    assert {s['code'] for s in client.get('/api/skus', params={'q': '博丽灵梦'}).json()} == {'BAD-01-A', 'ARC-01-A'}
    assert item['avatar_url'] == image
    assert next(s for s in client.get('/api/skus').json() if s['id'] == item['id'])['avatar_url'] == image
    cleared = client.patch('/api/skus/BAD-01-A', json={'avatar_url': None})
    assert cleared.status_code == 200 and cleared.json()['avatar_url'] is None
    assert next(s for s in client.get('/api/skus').json() if s['id'] == item['id'])['avatar_url'] is None


def test_stock_submission_and_approval(client):
    source = client.post('/api/stock-accounts', json=dict(name='商家', kind='external')).json()['id']
    target = client.post('/api/stock-accounts', json=dict(name='仓库', kind='internal')).json()['id']
    skus = [client.post('/api/skus', json=dict(code=f'ITEM-{index}', name=name, unit=unit)).json()['code'] for index, (name, unit) in enumerate( [('书', '本'), ('材料', '件')])]
    payload = dict(source_account_id=source, destination_account_id=target, effective_date='2026-10-13', source_reference='receipt:A', lines=[dict(sku_code=skus[0], quantity='2'), dict(sku_code=skus[1], quantity='125')])
    trusted = client.post('/api/stock-transfers', json=payload)
    assert trusted.status_code == 201
    trusted = trusted.json()
    assert trusted['status'] == 'in_transit' and trusted['approval_mode'] == 'automatic'
    assert {line['sku_code']: line['quantity'] for line in trusted['lines']} == {skus[0]: '2', skus[1]: '125'}
    assert client.patch(f'/api/skus/{skus[0]}', json={'unit': '套'}).status_code == 409
    assert client.patch(f'/api/skus/{skus[1]}', json={'quantity_scale': 2}).status_code == 422
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending_payload = payload
    pending = client.post('/api/stock-transfers', json=pending_payload).json()
    assert pending['status'] == 'pending'
    versions = dict()
    path = f"/api/stock-transfers/{pending['id']}/approve"
    assert client.post(path, json=versions).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    approved = client.post(path, json=versions).json()
    assert approved['status'] == 'in_transit' and approved['approval_mode'] == 'manual'
    assert client.post(path, json=versions).status_code == 409
    cancelled = client.post(f"/api/stock-transfers/{approved['id']}/cancel", json=dict(reason='另批登记')).json()
    assert cancelled['status'] == 'cancelled'
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending2 = client.post('/api/stock-transfers', json=pending_payload).json()
    with TestClient(create_app()) as actor:
        actor.post('/api/auth/login', json={'user_id': 'trusted'})
        client.post('/api/auth/login', json={'user_id': 'admin'})
        assert client.patch('/api/users/trusted', json={'role': 'untrusted'}).status_code == 200
        target_path = f"/api/stock-transfers/{pending2['id']}/approve"
        assert actor.post(target_path, json=dict()).status_code == 403
        assert client.patch('/api/users/trusted', json={'role': 'trusted', 'active': False}).status_code == 200
        assert actor.post(target_path, json=dict()).status_code in (401, 403)
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    assert client.get(f"/api/stock-transfers/{pending2['id']}").json()['status'] == 'pending'
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(StockTransfer)) == 3
        assert db.scalar(select(func.count()).select_from(StockTransferLine)) == 6
        assert db.scalar(select(func.count()).select_from(JournalLine)) == 0

def stock_setup(client):
    opening = client.post('/api/stock-accounts', json=dict(name='期初', kind='external')).json()['id']
    a, b = [client.post('/api/stock-accounts', json=dict(name=name, kind='internal')).json()['id'] for name in ('A', 'B')]
    skus = [client.post('/api/skus', json=dict(code=f'BOOK-{index}', name=name, unit='本')).json()['code'] for index, name in enumerate(('书', '册'))]
    return (opening, a, b, skus)

def stock_plan(client, source, target, skus, quantities, key, action='internal'):
    response = client.post('/api/stock-transfers', json=dict(source_account_id=source, destination_account_id=target, effective_date='2026-10-13', lines=[dict(sku_code=s, quantity=q) for s, q in zip(skus, quantities)]))
    assert response.status_code == 201, response.text
    return response.json()

def completion_data(item, key):
    return dict(effective_date='2026-10-13')

def complete(client, item, key):
    return client.post(f"/api/stock-transfers/{item['id']}/completion", json=completion_data(item, key))

def balances(client):
    return {(q['account_id'], q['sku_code']): q['quantity'] for q in client.get('/api/inventory').json()['items']}

def test_stock_completion_and_exact_inventory(client):
    opening, a, b, skus = stock_setup(client)
    assert all((q == '0' for q in balances(client).values()))
    incoming = stock_plan(client, opening, a, skus, ['100', '10'], 'opening', 'opening')
    assert complete(client, incoming, 'opening-complete').json()['status'] == 'completed'
    from backend.infrastructure import stock_store
    with Session() as db:
        actual = stock_store.available(db, a, stock_store.get_sku_by_code(db, skus[0]).id)
        zero = stock_store.available(db, b, stock_store.get_sku_by_code(db, skus[0]).id)
        assert type(actual) is int and actual == 100
        assert type(zero) is int and zero == 0
    first = stock_plan(client, a, b, skus, ['30', '2'], 'batch1')
    second = stock_plan(client, a, b, skus, ['20', '3'], 'batch2')
    assert balances(client)[a, skus[0]] == '100' and balances(client)[b, skus[0]] == '0'
    result = complete(client, first, 'batch1-complete')
    assert result.status_code == 200 and result.json()['status'] == 'completed'
    assert balances(client)[a, skus[0]] == '70' and balances(client)[b, skus[0]] == '30'
    assert balances(client)[a, skus[1]] == '8' and balances(client)[b, skus[1]] == '2'
    assert complete(client, first, 'batch1-complete').status_code == 409
    assert complete(client, second, 'batch2-complete').status_code == 200
    totals = {q['sku_code']: q['quantity'] for q in client.get('/api/inventory').json()['totals']}
    assert totals == {skus[0]: '100', skus[1]: '10'}
    assert len(client.get('/api/stock-moves').json()['items']) == 6
    assert all((location != opening for location, sku in balances(client)))
    bad = stock_plan(client, a, b, skus, ['1', '9'], 'insufficient')
    before = balances(client)
    assert complete(client, bad, 'fail').status_code == 409
    assert balances(client) == before
    assert client.get(f"/api/stock-transfers/{bad['id']}").json()['confirmations'] == []

def test_stock_confirmation_permissions_and_cancel(client):
    opening, a, b, skus = stock_setup(client)
    item = stock_plan(client, opening, a, skus, ['100', '10'], 'opening', 'opening')
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    data = completion_data(item, 'ordinary')
    pending = client.post(f"/api/stock-transfers/{item['id']}/completion", json=data).json()
    assert all((q == '0' for q in balances(client).values()))
    confirmation = pending['confirmations'][0]
    decision = dict()
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path, json=decision).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(path.replace('/approve', '/reject'), json=decision | {'reason': '重新核对'}).json()['status'] == 'in_transit'
    current = client.get(f"/api/stock-transfers/{item['id']}").json()
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = complete(client, current, 'ordinary2').json()
    confirmation = pending['confirmations'][-1]
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    decision = dict()
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path, json=decision).json()['status'] == 'completed'
    assert client.post(path, json=decision).status_code == 409
    assert balances(client)[a, skus[0]] == '100'
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert complete(client, current, 'ordinary2').status_code == 409
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    other = stock_plan(client, a, b, skus, ['1', '1'], 'cancelled')
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = complete(client, other, 'cancel-request').json()
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    decision = dict()
    assert client.post(f"/api/stock-transfers/{other['id']}/cancel", json=decision | {'reason': '作废'}).json()['confirmations'][0]['status'] == 'invalidated'
    assert client.post(f"/api/stock-confirmations/{pending['confirmations'][0]['id']}/approve", json=decision).status_code == 409

def test_stock_move_failure_rolls_back(client):
    import pytest
    from sqlalchemy import text
    from backend.infrastructure.database import engine
    opening, a, b, skus = stock_setup(client)
    item = stock_plan(client, opening, a, skus, ['100', '10'], 'opening', 'opening')
    before = client.get(f"/api/stock-transfers/{item['id']}").json()
    with engine.begin() as db:
        db.execute(text("CREATE FUNCTION fail_stock_move() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF (SELECT count(*) FROM stock_moves) > 0 THEN RAISE EXCEPTION 'induced stock failure'; END IF; RETURN NEW; END $$"))
        db.execute(text('CREATE TRIGGER fail_stock_move BEFORE INSERT ON stock_moves FOR EACH ROW EXECUTE FUNCTION fail_stock_move()'))
    try:
        with pytest.raises(Exception, match='induced stock failure'):
            complete(client, item, 'rollback')
        after = client.get(f"/api/stock-transfers/{item['id']}").json()
        assert {k: v for k, v in after.items() if k != 'snapshot_at'} == {k: v for k, v in before.items() if k != 'snapshot_at'}
        assert client.get('/api/stock-moves').json()['items'] == []
        assert all((q == '0' for q in balances(client).values()))
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_stock_move ON stock_moves'))
            db.execute(text('DROP FUNCTION fail_stock_move()'))
    assert complete(client, item, 'rollback').json()['status'] == 'completed'
    assert complete(client, item, 'rollback').status_code == 409
    assert len(client.get('/api/stock-moves').json()['items']) == 2

def test_stock_competing_completions(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.application import warehouse
    from backend.infrastructure import store
    from backend.kernel.accounting import DomainError
    opening, a, b, skus = stock_setup(client)
    incoming = stock_plan(client, opening, a, skus[:1], ['100'], 'opening', 'opening')
    assert complete(client, incoming, 'opening-complete').status_code == 200
    items = [stock_plan(client, a, b, skus[:1], ['70'], f'batch{i}') for i in range(2)]
    barrier = Barrier(2)

    def run(index):
        try:
            with Session.begin() as db:
                original = db.get(StockTransfer, items[index]['id'])
                user = store.get_user(db, 'trusted')
                barrier.wait(timeout=5)
                warehouse.request_completion(db, user, original.id, completion_data(items[index], f'compete{index}'))
            return 200
        except DomainError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(run, [0, 1]))
    assert sorted(results) == [200, 409]
    assert balances(client)[a, skus[0]] == '30' and balances(client)[b, skus[0]] == '70'
    assert len(client.get('/api/stock-moves').json()['items']) == 2

def test_transfer_loss_adjustments_and_custody(client):
    opening, a, b, skus = stock_setup(client)
    loss = client.post('/api/stock-accounts', json=dict(name='盘亏', kind='external')).json()['id']
    assert complete(client, stock_plan(client, opening, a, skus[:1], ['100'], 'opening', 'opening'), 'open').status_code == 200
    original = complete(client, stock_plan(client, a, b, skus[:1], ['30'], 'move'), 'finished').json()
    data = dict(source_account_id=b, destination_account_id=loss, effective_date='2026-10-13', related_transfer_id=original['id'], lines=[dict(sku_code=skus[0], quantity='2')])
    adjustment = client.post('/api/stock-transfers', json=data).json()
    assert balances(client)[b, skus[0]] == '30'
    assert complete(client, adjustment, 'adjustment').status_code == 200
    assert balances(client)[a, skus[0]] == '70' and balances(client)[b, skus[0]] == '28'
    assert client.get('/api/inventory', params={'sku_code': skus[0]}).json()['totals'][0]['quantity'] == '98'
    assert client.get(f"/api/stock-transfers/{original['id']}").json()['related_transfers'][0]['id'] == adjustment['id']
    members = [client.post('/api/members', json={'name': name}).json() for name in ('旧保管人', '新保管人')]
    for member in members:
        assert client.patch(f'/api/stock-accounts/{b}', json={'member_id': member['id']}).status_code == 200
        current = client.get('/api/inventory', params={'member_id': member['id'], 'sku_code': skus[0]}).json()
        assert current['totals'][0]['quantity'] == '28' and current['items'][0]['member_name'] == member['name']
    assert client.get('/api/inventory', params={'member_id': members[0]['id']}).json()['items'] == []


def test_stock_responsible_history_and_inventory(client):
    from sqlalchemy import func, select
    from backend.infrastructure.models import StockMove

    opening, a, b, skus = stock_setup(client)
    people = [client.post('/api/members', json={'name': name}).json() for name in ('小王', '小李')]
    account = client.post('/api/stock-accounts', json={
        'name': '成员代管处', 'kind': 'internal', 'member_id': people[0]['id'],
    }).json()
    path = '/api/stock-accounts/' + account['id']
    response = client.get(path)
    assert response.status_code == 200, response.text
    history = response.json()['responsibility_history']
    assert len(history) == 1 and history[0]['member_name'] == '小王'
    assert history[0]['actor_id'] == 'trusted' and history[0]['valid_to'] is None
    assert complete(client, stock_plan(client, opening, account['id'], skus[:1], ['5'], '入库'), '到货').status_code == 200
    before = balances(client)
    with Session() as db:
        move_count = db.scalar(select(func.count()).select_from(StockMove))

    assert client.patch(path, json={'member_id': people[0]['id']}).status_code == 200
    assert len(client.get(path).json()['responsibility_history']) == 1
    changed = client.patch(path, json={'member_id': people[1]['id']}).json()
    assert changed['member_id'] == people[1]['id'] and changed['member_name'] == '小李'
    history = client.get(path).json()['responsibility_history']
    assert [row['member_name'] for row in history] == ['小王', '小李']
    assert history[0]['valid_to'] == history[1]['valid_from']
    assert history[0]['ended_by'] == 'trusted' and history[0]['ended_by_name'] == '受信任成员'
    assert history[1]['actor_name'] == '受信任成员'
    current = client.get('/api/inventory', params={'member_id': people[1]['id'], 'sku_code': skus[0]}).json()
    assert current['totals'][0]['quantity'] == '5'
    assert client.get('/api/inventory', params={'member_id': people[0]['id']}).json()['items'] == []
    listed = client.get('/api/stock-accounts', params={'member_id': people[1]['id']}).json()
    assert [row['id'] for row in listed] == [account['id']]

    assert client.patch(path, json={'member_id': None}).json()['member_id'] is None
    history = client.get(path).json()['responsibility_history']
    assert len(history) == 2 and all(row['valid_to'] is not None for row in history)
    external = client.post('/api/stock-accounts', json={
        'name': '供应商端点', 'kind': 'external', 'member_id': people[0]['id'],
    }).json()
    assert client.get('/api/stock-accounts/' + external['id']).json()['responsibility_history'][0]['member_id'] == people[0]['id']
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.patch(path, json={'member_id': people[0]['id']}).status_code == 403
    assert client.get(path).status_code == 200
    assert balances(client) == before
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(StockMove)) == move_count

def test_under_shipped_independent_endpoint_adjustments(client):
    opening, a, b, skus = stock_setup(client)
    boundaries = {kind: client.post('/api/stock-accounts', json=dict(name=kind, kind='external')).json()['id'] for kind in ('adjustment_gain', 'adjustment_loss')}
    assert complete(client, stock_plan(client, opening, a, skus[:1], ['100'], 'opening', 'opening'), 'open').status_code == 200
    original = complete(client, stock_plan(client, a, b, skus[:1], ['30'], 'move'), 'move-complete').json()
    for location, kind in ((a, 'adjustment_gain'), (b, 'adjustment_loss')):
        source, target = (boundaries[kind], location) if kind == 'adjustment_gain' else (location, boundaries[kind])
        adjustment = client.post('/api/stock-transfers', json=dict(source_account_id=source, destination_account_id=target, effective_date='2026-10-13', related_transfer_id=original['id'], lines=[dict(sku_code=skus[0], quantity='2')])).json()
        assert complete(client, adjustment, kind).status_code == 200
    assert balances(client)[a, skus[0]] == '72' and balances(client)[b, skus[0]] == '28'
    assert client.get('/api/inventory', params={'sku_code': skus[0]}).json()['totals'][0]['quantity'] == '100'

def operation_payload(client):
    source = client.post('/api/stock-accounts', json=dict(name='供应商', kind='external')).json()['id']
    target = client.post('/api/stock-accounts', json=dict(name='仓库', kind='internal')).json()['id']
    sku = client.post('/api/skus', json=dict(code='BOOK-01-A', name='书', unit='本')).json()['code']
    return dict(stock=dict(source_account_id=source, destination_account_id=target, effective_date='2026-10-13', lines=[dict(sku_code=sku, quantity='100')]), money=dict(source_account_id='fund_pool', destination_account_id='expense', amount='1000', effective_date='2026-10-13'))

def test_money_first_operation_and_independent_completion(client):
    from backend.tests.test_funds import transfer
    from backend.infrastructure.models import Transfer
    assert transfer(client, 'opening', 'fund_pool', '2000').status_code == 201
    payload = operation_payload(client)
    response = client.post('/api/stock-operations', json=payload)
    assert response.status_code == 201, response.text
    result = response.json()
    stock, money = (result['stock_transfer'], result['fund_transfer'])
    assert money['status'] == 'posted' and stock['status'] == 'in_transit'
    assert stock['fund_references'][0]['id'] == money['id']
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    assert client.get('/api/stock-moves').json()['items'] == []
    finished = complete(client, stock, 'arrived').json()
    assert finished['status'] == 'completed'
    assert complete(client, stock, 'arrived').status_code == 409
    assert balances(client) == {('main', stock['lines'][0]['sku_code']): '0', (stock['destination_account_id'], stock['lines'][0]['sku_code']): '100'}
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    assert client.post('/api/stock-operations', json=payload | {'stock': payload['stock'] | {'fund_transfer_ids': [money['id']]}}).status_code == 400
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 2

def test_combined_operation_database_failures_leave_no_halves(client):
    import pytest
    from sqlalchemy import text
    from backend.infrastructure.database import engine
    from backend.infrastructure.models import Transfer, Audit, StockAudit, StockTransferFundReference
    payload = operation_payload(client)
    tables = [Transfer, JournalLine, Audit, StockTransfer, StockTransferLine, StockAudit, StockTransferFundReference]
    for target in ('journal_lines', 'stock_transfer_lines'):
        with engine.begin() as db:
            db.execute(text("CREATE FUNCTION fail_combined() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'induced combined failure'; END $$"))
            db.execute(text(f'CREATE TRIGGER fail_combined BEFORE INSERT ON {target} FOR EACH ROW EXECUTE FUNCTION fail_combined()'))
        try:
            for request in (payload,):
                with pytest.raises(Exception, match='induced combined failure'):
                    client.post('/api/stock-operations', json=request)
                with Session() as db:
                    assert all((db.scalar(select(func.count()).select_from(table)) == 0 for table in tables))
        finally:
            with engine.begin() as db:
                db.execute(text(f'DROP TRIGGER fail_combined ON {target}'))
                db.execute(text('DROP FUNCTION fail_combined()'))
    assert client.post('/api/stock-operations', json=payload).status_code == 201

def test_stock_stocktake_ordinary_completion_and_end(client, monkeypatch):
    from backend.application import stocktakes
    monkeypatch.setattr(stocktakes, 'ENABLED', True)
    target = client.post('/api/stock-accounts', json={'name': '书库', 'kind': 'internal'}).json()['id']
    sku = client.post('/api/skus', json={'code': 'BOOK-01-A', 'name': '书', 'unit': '本'}).json()['code']
    response = client.post('/api/stock-stocktakes', json={'name': '期末盘点'})
    assert response.status_code == 201
    item = response.json()
    path = f"/api/stock-stocktakes/{item['id']}"
    locations = {l['id']: l for l in client.get('/api/stock-accounts').json()}
    assert locations[target]['stocktake'] is None
    for endpoint in ('gain_account_id', 'loss_account_id'):
        assert locations[item[endpoint]]['stocktake'] == {'id': item['id'], 'name': item['name'], 'status': 'in_progress'}
    assert balances(client)[target, sku] == '0'
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    gain = stock_plan(client, item['gain_account_id'], target, [sku], ['10'], 'gain', action='adjustment_gain')
    assert gain['status'] == 'pending'
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f"/api/stock-transfers/{gain['id']}/approve", json={}).json()['status'] == 'in_transit'
    assert balances(client)[target, sku] == '0'
    assert complete(client, gain, 'gain').status_code == 200
    assert balances(client)[target, sku] == '10'
    loss = stock_plan(client, target, item['loss_account_id'], [sku], ['2'], 'loss', action='adjustment_loss')
    assert complete(client, loss, 'loss').status_code == 200
    assert balances(client)[target, sku] == '8'
    assert {t['id'] for t in client.get(path).json()['transfers']} == {gain['id'], loss['id']}
    assert client.post(path + '/end').json()['status'] == 'ended'
    locations = {l['id']: l for l in client.get('/api/stock-accounts').json()}
    assert all((locations[item[key]]['stocktake']['status'] == 'ended' for key in ('gain_account_id', 'loss_account_id')))
    later = stock_plan(client, item['gain_account_id'], target, [sku], ['1'], 'later', action='adjustment_gain')
    assert complete(client, later, 'later').status_code == 200
    assert balances(client)[target, sku] == '9'
    assert {t['id'] for t in client.get(path).json()['transfers']} == {gain['id'], loss['id'], later['id']}
    correction=stock_plan(client,target,item['gain_account_id'],[sku],['1'],'反向更正')
    assert complete(client,correction,'correction').status_code==200
    assert balances(client)[target,sku]=='8'
    assert {t['id'] for t in client.get(path).json()['transfers']} == {gain['id'],loss['id'],later['id'],correction['id']}


def test_free_tags_links_and_disabled_existing_completion(client):
    external,a,b,skus=stock_setup(client)
    original=stock_plan(client,external,a,skus[:1],['5'],'old')
    linked=client.post('/api/stock-transfers',json={'source_account_id':external,'destination_account_id':b,'effective_date':'2026-10-14','related_transfer_id':original['id'],'tags':['游客','自由用途'],'lines':[{'sku_code':skus[1],'quantity':'3'}]})
    assert linked.status_code==201,linked.text
    item=linked.json()
    assert client.get('/api/stock-transfers?tag=自由用途').json()['items'][0]['id']==item['id']
    assert client.patch(f'/api/stock-accounts/{b}',json={'kind':'external'}).status_code==422
    assert client.patch(f'/api/stock-accounts/{b}',json={'active':False}).status_code==200
    assert client.patch(f'/api/skus/{skus[1]}',json={'active':False}).status_code==200
    assert complete(client,item,'done').status_code==200
    assert balances(client)[b,skus[1]]=='3'
    assert client.post('/api/stock-transfers',json={'source_account_id':external,'destination_account_id':b,'effective_date':'2026-10-14','lines':[{'sku_code':skus[0],'quantity':'1'}]}).status_code==409


def test_stock_invalid_quantity_and_empty_or_duplicate_lines(client):
    external,a,b,skus=stock_setup(client)
    base={'source_account_id':external,'destination_account_id':a,'effective_date':'2026-10-14'}
    for quantity in ('0','-1','1.1','9007199254740992'):
        assert client.post('/api/stock-transfers',json=base|{'lines':[{'sku_code':skus[0],'quantity':quantity}]}).status_code==400
    assert client.post('/api/stock-transfers',json=base|{'lines':[]}).status_code==422
    assert client.post('/api/stock-transfers',json=base|{'lines':[{'sku_code':skus[0],'quantity':'1'}]*2}).status_code==400
    assert client.get('/api/stock-transfers').json()['items']==[]


def test_stock_list_pagination_search_and_attention(client):
    source = client.post('/api/stock-accounts', json=dict(name='商家', kind='external')).json()['id']
    target = client.post('/api/stock-accounts', json=dict(name='仓库', kind='internal')).json()['id']
    sku = client.post('/api/skus', json=dict(code='BOOK-01-A', name='书', unit='本')).json()['code']
    payload = dict(source_account_id=source, destination_account_id=target, effective_date='2026-10-13',
                   lines=[dict(sku_code=sku, quantity='1')])
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    first = client.post('/api/stock-transfers', json=payload).json()
    client.post('/api/stock-transfers', json=payload)
    page = client.get('/api/stock-transfers', params={'page': 1, 'limit': 1}).json()
    assert page['total'] == 2 and len(page['items']) == 1
    assert client.get('/api/stock-transfers', params={'q': '仓库'}).json()['total'] == 2
    assert client.get('/api/stock-transfers', params={'attention': 'true'}).json()['total'] == 2
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f"/api/stock-transfers/{first['id']}/approve", json={}).status_code == 200
    assert client.get('/api/stock-transfers', params={'attention': 'true'}).json()['total'] == 1
