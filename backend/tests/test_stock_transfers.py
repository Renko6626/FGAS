"""Real stock submission/approval paths; isolated PostgreSQL fixture only."""
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.entrypoints.http import app
from backend.infrastructure.database import Session
from backend.infrastructure.models import StockTransfer, StockTransferLine, JournalLine


def test_stock_submission_and_approval(client):
    source = client.post('/api/locations', json=dict(name='商家', kind='external', external_kind='supplier')).json()['id']
    target = client.post('/api/locations', json=dict(name='仓库')).json()['id']
    skus = [client.post('/api/skus', json=dict(name=name, unit=unit)).json()['id'] for name, unit in [('书','本'),('材料','件')]]
    payload = dict(source_location_id=source, destination_location_id=target, action_kind='arrival', effective_date='2026-10-13', basis='到货单 A', source_reference='receipt:A', lines=[dict(sku_id=skus[0], quantity='2'),dict(sku_id=skus[1],quantity='125')])
    trusted = client.post('/api/stock-transfers', json=payload)
    assert trusted.status_code == 201
    trusted = trusted.json()
    assert trusted['status'] == 'in_transit' and trusted['approval_mode'] == 'automatic'
    assert {line['sku_id']: line['quantity'] for line in trusted['lines']} == {skus[0]:'2',skus[1]:'125'}
    assert trusted['approval_snapshot']['lines'] == trusted['lines']
    assert client.patch(f'/api/skus/{skus[0]}', json={'unit':'套'}).status_code == 409
    assert client.patch(f'/api/skus/{skus[1]}', json={'quantity_scale':2}).status_code == 422
    assert client.patch(f'/api/locations/{source}', json={'external_kind':'customer'}).status_code == 409
    assert client.patch(f'/api/locations/{target}', json={'kind':'external','external_kind':'customer'}).status_code == 409
    client.post('/api/auth/login', json={'user_id':'untrusted'})
    pending_payload = payload
    pending = client.post('/api/stock-transfers', json=pending_payload).json()
    assert pending['status'] == 'pending' and pending['approval_snapshot'] is None
    versions = dict()
    path = f"/api/stock-transfers/{pending['id']}/approve"
    assert client.post(path, json=versions).status_code == 403
    client.post('/api/auth/login', json={'user_id':'trusted'})
    approved = client.post(path, json=versions).json()
    assert approved['status'] == 'in_transit' and approved['approval_mode'] == 'manual'
    assert client.post(path, json=versions).status_code == 409
    cancelled = client.post(f"/api/stock-transfers/{approved['id']}/cancel", json=dict( reason='另批登记')).json()
    assert cancelled['status'] == 'cancelled'
    client.post('/api/auth/login', json={'user_id':'untrusted'})
    pending2 = client.post('/api/stock-transfers', json=pending_payload).json()
    # Keep an existing trusted session while admin changes its authority.
    with TestClient(app) as actor:
        actor.post('/api/auth/login', json={'user_id':'trusted'})
        client.post('/api/auth/login', json={'user_id':'admin'})
        assert client.patch('/api/users/trusted', json={'role':'untrusted'}).status_code == 200
        target_path = f"/api/stock-transfers/{pending2['id']}/approve"
        assert actor.post(target_path, json=dict()).status_code == 403
        assert client.patch('/api/users/trusted', json={'role':'trusted','active':False}).status_code == 200
        assert actor.post(target_path, json=dict()).status_code in (401,403)
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    assert client.get(f"/api/stock-transfers/{pending2['id']}").json()['status'] == 'pending'
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(StockTransfer)) == 3
        assert db.scalar(select(func.count()).select_from(StockTransferLine)) == 6
        assert db.scalar(select(func.count()).select_from(JournalLine)) == 0


def test_stock_invalid_contents_and_terminal_actions(client):
    source = client.post('/api/locations', json=dict(name='期初',kind='external',external_kind='opening')).json()['id']
    target = client.post('/api/locations', json=dict(name='仓库')).json()['id']
    sku = client.post('/api/skus', json=dict(name='书',unit='本')).json()['id']
    data = dict(source_location_id=source,destination_location_id=target,action_kind='opening',effective_date='2026-10-13',basis='期初单',lines=[dict(sku_id=sku,quantity='2')])
    for patch in ({'action_kind':'internal'}, {'action_kind':'adjustment_gain'}, {'destination_location_id':source}, {'fund_transfer_ids':['missing']}, {'lines':[dict(sku_id=sku,quantity='2'),dict(sku_id=sku,quantity='1')]}, *({'lines':[dict(sku_id=sku,quantity=q)]} for q in ['0','-1','1e2','1.1','1.0','１２','9007199254740992'])):
        assert client.post('/api/stock-transfers',json=data | patch).status_code in (400,404,409)
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = client.post('/api/stock-transfers',json=data).json()
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict(reason='依据有误')
    path = f"/api/stock-transfers/{pending['id']}/reject"
    assert client.post(path,json=decision).json()['status'] == 'rejected'
    assert client.post(path,json=decision).status_code == 409
    assert client.post(path,json=decision | {'reason':'另一个原因'}).status_code == 409


def stock_setup(client):
    opening = client.post('/api/locations', json=dict(name='期初', kind='external', external_kind='opening')).json()['id']
    a, b = [client.post('/api/locations', json=dict(name=name)).json()['id'] for name in ('A','B')]
    skus = [client.post('/api/skus', json=dict(name=name,unit='本')).json()['id'] for name in ('书','册')]
    return opening, a, b, skus


def stock_plan(client, source, target, skus, quantities, key, action='internal'):
    response = client.post('/api/stock-transfers', json=dict(source_location_id=source,destination_location_id=target,action_kind=action,effective_date='2026-10-13',basis='核对单',lines=[dict(sku_id=s,quantity=q) for s,q in zip(skus,quantities)]))
    assert response.status_code == 201, response.text
    return response.json()


def completion_data(item, key):
    return dict(effective_date='2026-10-13',basis='实物核对')


def complete(client, item, key):
    return client.post(f"/api/stock-transfers/{item['id']}/completion", json=completion_data(item,key))


def balances(client):
    return {(q['location_id'],q['sku_id']):q['quantity'] for q in client.get('/api/inventory').json()['quantities']}


def test_stock_completion_and_exact_inventory(client):
    opening,a,b,skus = stock_setup(client)
    assert all(q == '0' for q in balances(client).values())
    incoming = stock_plan(client,opening,a,skus,['100','10'],'opening','opening')
    assert complete(client,incoming,'opening-complete').json()['status'] == 'completed'
    from backend.infrastructure import stock_store
    with Session() as db:
        actual = stock_store.available(db,a,skus[0])
        zero = stock_store.available(db,b,skus[0])
        assert type(actual) is int and actual == 100
        assert type(zero) is int and zero == 0
    first = stock_plan(client,a,b,skus,['30','2'],'batch1')
    second = stock_plan(client,a,b,skus,['20','3'],'batch2')
    assert balances(client)[a,skus[0]] == '100' and balances(client)[b,skus[0]] == '0'
    result = complete(client,first,'batch1-complete')
    assert result.status_code == 200 and result.json()['status'] == 'completed'
    assert balances(client)[a,skus[0]] == '70' and balances(client)[b,skus[0]] == '30'
    assert balances(client)[a,skus[1]] == '8' and balances(client)[b,skus[1]] == '2'
    assert complete(client,first,'batch1-complete').status_code == 409
    assert complete(client,second,'batch2-complete').status_code == 200
    totals = {q['sku_id']:q['quantity'] for q in client.get('/api/inventory').json()['totals']}
    assert totals == {skus[0]:'100',skus[1]:'10'}
    assert len(client.get('/api/stock-moves').json()) == 6
    assert all(location != opening for location,sku in balances(client))
    bad = stock_plan(client,a,b,skus,['1','9'],'insufficient')
    before = balances(client)
    assert complete(client,bad,'fail').status_code == 409
    assert balances(client) == before
    assert client.get(f"/api/stock-transfers/{bad['id']}").json()['confirmations'] == []


def test_stock_confirmation_permissions_and_cancel(client):
    opening,a,b,skus = stock_setup(client)
    item = stock_plan(client,opening,a,skus,['100','10'],'opening','opening')
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    data = completion_data(item,'ordinary')
    pending = client.post(f"/api/stock-transfers/{item['id']}/completion",json=data).json()
    assert all(q == '0' for q in balances(client).values())
    confirmation = pending['confirmations'][0]
    decision = dict()
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path,json=decision).status_code == 403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert client.post(path.replace('/approve','/reject'),json=decision | {'reason':'重新核对'}).json()['status'] == 'in_transit'
    current = client.get(f"/api/stock-transfers/{item['id']}").json()
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = complete(client,current,'ordinary2').json()
    confirmation = pending['confirmations'][-1]
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict()
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path,json=decision).json()['status'] == 'completed'
    assert client.post(path,json=decision).status_code == 409
    assert balances(client)[a,skus[0]] == '100'
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    assert complete(client,current,'ordinary2').status_code == 409
    client.post('/api/auth/login',json={'user_id':'trusted'})
    other = stock_plan(client,a,b,skus,['1','1'],'cancelled')
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = complete(client,other,'cancel-request').json()
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict()
    assert client.post(f"/api/stock-transfers/{other['id']}/cancel",json=decision | {'reason':'作废'}).json()['confirmations'][0]['status'] == 'invalidated'
    assert client.post(f"/api/stock-confirmations/{pending['confirmations'][0]['id']}/approve",json=decision).status_code == 409


def test_stock_move_failure_rolls_back(client):
    import pytest
    from sqlalchemy import text
    from backend.infrastructure.database import engine
    opening,a,b,skus = stock_setup(client)
    item = stock_plan(client,opening,a,skus,['100','10'],'opening','opening')
    before = client.get(f"/api/stock-transfers/{item['id']}").json()
    with engine.begin() as db:
        db.execute(text("CREATE FUNCTION fail_stock_move() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF (SELECT count(*) FROM stock_moves) > 0 THEN RAISE EXCEPTION 'induced stock failure'; END IF; RETURN NEW; END $$"))
        db.execute(text('CREATE TRIGGER fail_stock_move BEFORE INSERT ON stock_moves FOR EACH ROW EXECUTE FUNCTION fail_stock_move()'))
    try:
        with pytest.raises(Exception,match='induced stock failure'): complete(client,item,'rollback')
        after = client.get(f"/api/stock-transfers/{item['id']}").json()
        assert {k:v for k,v in after.items() if k != 'snapshot_at'} == {k:v for k,v in before.items() if k != 'snapshot_at'}
        assert client.get('/api/stock-moves').json() == []
        assert all(q == '0' for q in balances(client).values())
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_stock_move ON stock_moves'))
            db.execute(text('DROP FUNCTION fail_stock_move()'))
    assert complete(client,item,'rollback').json()['status'] == 'completed'
    assert complete(client,item,'rollback').status_code == 409
    assert len(client.get('/api/stock-moves').json()) == 2


def test_stock_competing_completions(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.application import warehouse
    from backend.infrastructure import store
    from backend.kernel.accounting import DomainError
    opening,a,b,skus = stock_setup(client)
    incoming = stock_plan(client,opening,a,skus[:1],['100'],'opening','opening')
    assert complete(client,incoming,'opening-complete').status_code == 200
    items = [stock_plan(client,a,b,skus[:1],['70'],f'batch{i}') for i in range(2)]
    barrier = Barrier(2)
    def run(index):
        try:
            with Session.begin() as db:
                original = db.get(StockTransfer,items[index]['id'])
                user = store.get_user(db,'trusted')
                barrier.wait(timeout=5)
                warehouse.request_completion(db,user,original.id,completion_data(items[index],f'compete{index}'))
            return 200
        except DomainError as error: return error.status
    with ThreadPoolExecutor(max_workers=2) as workers: results = list(workers.map(run,[0,1]))
    assert sorted(results) == [200,409]
    assert balances(client)[a,skus[0]] == '30' and balances(client)[b,skus[0]] == '70'
    assert len(client.get('/api/stock-moves').json()) == 2


def test_transfer_loss_adjustments_and_custody(client):
    opening,a,b,skus = stock_setup(client)
    loss = client.post('/api/locations',json=dict(name='盘亏',kind='external',external_kind='adjustment_loss')).json()['id']
    assert complete(client,stock_plan(client,opening,a,skus[:1],['100'],'opening','opening'),'open').status_code == 200
    original = complete(client,stock_plan(client,a,b,skus[:1],['30'],'move'),'finished').json()
    data = dict(source_location_id=b,destination_location_id=loss,action_kind='adjustment_loss',effective_date='2026-10-13',basis='核对盘亏',related_transfer_id=original['id'],lines=[dict(sku_id=skus[0],quantity='2')])
    adjustment = client.post('/api/stock-transfers',json=data).json()
    assert balances(client)[b,skus[0]] == '30'
    assert complete(client,adjustment,'adjustment').status_code == 200
    assert balances(client)[a,skus[0]] == '70' and balances(client)[b,skus[0]] == '28'
    assert client.get('/api/inventory',params={'sku_id':skus[0]}).json()['totals'][0]['quantity'] == '98'
    assert client.get(f"/api/stock-transfers/{original['id']}").json()['adjustments'][0]['id'] == adjustment['id']
    members = [client.post('/api/members',json={'name':name}).json() for name in ('旧保管人','新保管人')]
    for member in members:
        assert client.post(f'/api/locations/{b}/custody',json={'member_id':member['id']}).status_code == 200
        current = client.get('/api/inventory',params={'member_id':member['id'],'sku_id':skus[0]}).json()
        assert current['totals'][0]['quantity'] == '28' and current['quantities'][0]['member_name'] == member['name']
    assert client.get('/api/inventory',params={'member_id':members[0]['id']}).json()['quantities'] == []


def test_under_shipped_independent_endpoint_adjustments(client):
    opening,a,b,skus = stock_setup(client)
    boundaries = {kind:client.post('/api/locations',json=dict(name=kind,kind='external',external_kind=kind)).json()['id'] for kind in ('adjustment_gain','adjustment_loss')}
    assert complete(client,stock_plan(client,opening,a,skus[:1],['100'],'opening','opening'),'open').status_code == 200
    original = complete(client,stock_plan(client,a,b,skus[:1],['30'],'move'),'move-complete').json()
    for location,kind in ((a,'adjustment_gain'),(b,'adjustment_loss')):
        source,target = (boundaries[kind],location) if kind == 'adjustment_gain' else (location,boundaries[kind])
        adjustment = client.post('/api/stock-transfers',json=dict(source_location_id=source,destination_location_id=target,action_kind=kind,effective_date='2026-10-13',basis='少发两本仍在来源',related_transfer_id=original['id'],lines=[dict(sku_id=skus[0],quantity='2')])).json()
        assert complete(client,adjustment,kind).status_code == 200
    assert balances(client)[a,skus[0]] == '72' and balances(client)[b,skus[0]] == '28'
    assert client.get('/api/inventory',params={'sku_id':skus[0]}).json()['totals'][0]['quantity'] == '100'


def test_stock_fund_references_do_not_change_money(client):
    from backend.tests.test_member_claims import member,claim_payload,repayment_payload
    m = member(client)
    claim = client.post('/api/member-claims',json=claim_payload(m,'fund_pool',confirm=True)).json()
    assert claim['confirmed_minor'] == 100000
    repayment = client.post('/api/repayments',json=repayment_payload(client, m, '100')).json()
    baseline = (client.get('/api/funds/summary').json(),client.get(f"/api/members/{m['id']}").json(),client.get(f"/api/member-claims/{claim['id']}").json(),client.get('/api/repayments').json())
    source = client.post('/api/locations',json=dict(name='供应商',kind='external',external_kind='supplier')).json()['id']
    target = client.post('/api/locations',json=dict(name='仓库')).json()['id']
    sku = client.post('/api/skus',json=dict(name='书',unit='本')).json()['id']
    receipts = [stock_plan(client,source,target,[sku],['10'],f'receipt{i}','arrival') for i in range(2)]
    for i,item in enumerate(receipts):
        assert complete(client,item,f'complete{i}').status_code == 200
        path = f"/api/stock-transfers/{item['id']}/fund-references"
        data = dict(fund_transfer_id=claim['id'])
        client.post('/api/auth/login',json={'user_id':'untrusted'})
        assert client.post(path,json=data).status_code == 403
        client.post('/api/auth/login',json={'user_id':'trusted'})
        linked = client.post(path,json=data).json()
        assert linked['fund_references'][0]['business_type'] == 'member_claim'
        assert linked['fund_references'][0]['member_id'] == m['id'] and linked['fund_references'][0]['status'] == 'posted'
        assert client.post(path,json=data).status_code == 200
        assert len(client.post(path,json=data).json()['fund_references']) == 1
        assert client.post(path,json={'fund_transfer_id':'missing'}).status_code == 404
    assert (client.get('/api/funds/summary').json(),client.get(f"/api/members/{m['id']}").json(),client.get(f"/api/member-claims/{claim['id']}").json(),client.get('/api/repayments').json()) == baseline
    # Reverse the matched repayment first, then claim; stock links survive both money facts.
    assert client.post(f"/api/transfers/{repayment['id']}/reverse",json=dict(reason='退回偿还')).status_code == 201
    assert client.post(f"/api/transfers/{claim['id']}/reverse",json=dict(reason='冲销垫付')).status_code == 201
    assert all(client.get(f"/api/stock-transfers/{item['id']}").json()['fund_references'][0]['status'] == 'reversed' for item in receipts)
    assert balances(client)[target,sku] == '20'


def operation_payload(client):
    source = client.post('/api/locations',json=dict(name='供应商',kind='external',external_kind='supplier')).json()['id']
    target = client.post('/api/locations',json=dict(name='仓库')).json()['id']
    sku = client.post('/api/skus',json=dict(name='书',unit='本')).json()['id']
    return dict(stock=dict(source_location_id=source,destination_location_id=target,
        action_kind='arrival',effective_date='2026-10-13',basis='到货单',lines=[dict(sku_id=sku,quantity='100')],
        ),money=dict(kind='fund_transfer',data=dict(source_account_id='fund_pool',
        destination_account_id='expense',amount='1000',effective_date='2026-10-13')))


def test_money_first_operation_and_independent_completion(client):
    from backend.tests.test_funds import transfer
    from backend.infrastructure.models import Transfer
    assert transfer(client, 'opening', 'fund_pool', '2000').status_code == 201
    payload = operation_payload(client)
    response = client.post('/api/stock-operations',json=payload)
    assert response.status_code == 201,response.text
    result = response.json()
    stock, money = result['stock_transfer'], result['fund_transfer']
    assert money['status'] == 'posted' and stock['status'] == 'in_transit'
    assert stock['fund_references'][0]['id'] == money['id']
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    assert client.get('/api/stock-moves').json() == []
    finished = complete(client,stock,'arrived').json()
    assert finished['status'] == 'completed'
    assert complete(client,stock,'arrived').status_code == 409
    assert list(balances(client).values()) == ['100']
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    assert client.post('/api/stock-operations',json=payload | {'stock':payload['stock'] | {'fund_transfer_ids':[money['id']]}}).status_code == 400
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Transfer)) == 2


def test_combined_claim_and_ordinary_approval_boundaries(client):
    from backend.tests.test_member_claims import member,claim_payload
    payload = operation_payload(client)
    m = member(client)
    claim_request = payload | {'money':dict(kind='member_claim',data=claim_payload(m,confirm=True))}
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    assert client.post('/api/stock-operations',json=claim_request).status_code == 403
    pending = client.post('/api/stock-operations',json=payload).json()
    assert pending['stock_transfer']['status'] == pending['fund_transfer']['status'] == 'pending'
    client.post('/api/auth/login',json={'user_id':'trusted'})
    money = pending['fund_transfer']
    assert client.post(f"/api/transfers/{money['id']}/approve",json=dict(expected_version=money['version'])).status_code == 200
    assert client.get(f"/api/stock-transfers/{pending['stock_transfer']['id']}").json()['status'] == 'pending'
    claim = client.post('/api/stock-operations',json=claim_request).json()
    assert claim['claim']['confirmed_minor'] == claim['claim']['outstanding_minor'] == 100000
    assert claim['fund_transfer']['status'] == 'posted'
    stock = claim['stock_transfer']
    assert stock['status'] == 'in_transit'
    assert client.post(f"/api/stock-transfers/{stock['id']}/cancel",json=dict(reason='未到货')).status_code == 200
    assert client.get(f"/api/member-claims/{claim['claim']['id']}").json()['status'] == 'posted'


def test_combined_operation_database_failures_leave_no_halves(client):
    import pytest
    from sqlalchemy import text
    from backend.infrastructure.database import engine
    from backend.infrastructure.models import Transfer,Audit,MemberClaim,StockAudit,StockTransferFundReference
    payload = operation_payload(client)
    from backend.tests.test_member_claims import member,claim_payload
    m = member(client)
    claim_request = payload | {'money':dict(kind='member_claim',data=claim_payload(m,confirm=True))}
    tables = [Transfer,JournalLine,Audit,MemberClaim,StockTransfer,StockTransferLine,StockAudit,StockTransferFundReference]
    for target in ('journal_lines','stock_transfer_lines'):
        with engine.begin() as db:
            db.execute(text("CREATE FUNCTION fail_combined() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'induced combined failure'; END $$"))
            db.execute(text(f'CREATE TRIGGER fail_combined BEFORE INSERT ON {target} FOR EACH ROW EXECUTE FUNCTION fail_combined()'))
        try:
            for request in (payload,claim_request):
                with pytest.raises(Exception,match='induced combined failure'):
                    client.post('/api/stock-operations',json=request)
                with Session() as db:
                    assert all(db.scalar(select(func.count()).select_from(table)) == 0 for table in tables)
        finally:
            with engine.begin() as db:
                db.execute(text(f'DROP TRIGGER fail_combined ON {target}'))
                db.execute(text('DROP FUNCTION fail_combined()'))
    assert client.post('/api/stock-operations',json=payload).status_code == 201


def test_stock_stocktake_ordinary_completion_and_end(client):
    target = client.post('/api/locations', json={'name': '书库'}).json()['id']
    sku = client.post('/api/skus', json={'name': '书', 'unit': '本'}).json()['id']
    response = client.post('/api/stock-stocktakes', json={'name': '期末盘点'})
    assert response.status_code == 201
    item = response.json()
    path = f"/api/stock-stocktakes/{item['id']}"
    locations = {l['id']: l for l in client.get('/api/locations').json()}
    assert locations[target]['stocktake'] is None
    for endpoint in ('gain_location_id', 'loss_location_id'):
        assert locations[item[endpoint]]['stocktake'] == {'id': item['id'], 'name': item['name'], 'status': 'in_progress'}
    assert client.patch(f"/api/locations/{item['gain_location_id']}", json={'external_kind': 'supplier'}).status_code == 409
    assert next(l for l in client.get('/api/locations').json() if l['id'] == item['gain_location_id'])['external_kind'] == 'adjustment_gain'
    assert balances(client)[target, sku] == '0'
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    gain = stock_plan(client, item['gain_location_id'], target, [sku], ['10'], 'gain', action='adjustment_gain')
    assert gain['status'] == 'pending'
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f"/api/stock-transfers/{gain['id']}/approve", json={}).json()['status'] == 'in_transit'
    assert balances(client)[target, sku] == '0'
    assert complete(client, gain, 'gain').status_code == 200
    assert balances(client)[target, sku] == '10'
    loss = stock_plan(client, target, item['loss_location_id'], [sku], ['2'], 'loss', action='adjustment_loss')
    assert complete(client, loss, 'loss').status_code == 200
    assert balances(client)[target, sku] == '8'
    assert {t['id'] for t in client.get(path).json()['transfers']} == {gain['id'], loss['id']}
    assert client.post(path + '/end').json()['status'] == 'ended'
    locations = {l['id']: l for l in client.get('/api/locations').json()}
    assert all(locations[item[key]]['stocktake']['status'] == 'ended' for key in ('gain_location_id', 'loss_location_id'))
    later = stock_plan(client, item['gain_location_id'], target, [sku], ['1'], 'later', action='adjustment_gain')
    assert complete(client, later, 'later').status_code == 200
    assert balances(client)[target, sku] == '9'
    assert {t['id'] for t in client.get(path).json()['transfers']} == {gain['id'], loss['id'], later['id']}
