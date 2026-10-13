"""Real stock submission/approval paths; isolated PostgreSQL fixture only."""
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.entrypoints.http import app
from backend.infrastructure.database import Session
from backend.infrastructure.models import StockTransfer, StockTransferLine, JournalLine


def test_stock_submission_approval_and_retry(client):
    source = client.post('/api/locations', json=dict(name='商家', kind='external', external_kind='supplier')).json()['id']
    target = client.post('/api/locations', json=dict(name='仓库')).json()['id']
    skus = [client.post('/api/skus', json=dict(name=name, unit=unit)).json()['id'] for name, unit in [('书','本'),('材料','件')]]
    payload = dict(source_location_id=source, destination_location_id=target, action_kind='arrival', effective_date='2026-10-13', basis='到货单 A', source_reference='receipt:A', lines=[dict(sku_id=skus[0], quantity='2'),dict(sku_id=skus[1],quantity='125')], idempotency_key='trusted')
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
    pending_payload = payload | {'idempotency_key':'ordinary'}
    pending = client.post('/api/stock-transfers', json=pending_payload).json()
    assert pending['status'] == 'pending' and pending['approval_snapshot'] is None
    versions = dict(expected_content_version=pending['content_version'],expected_execution_version=pending['execution_version'],idempotency_key='approval')
    path = f"/api/stock-transfers/{pending['id']}/approve"
    assert client.post(path, json=versions).status_code == 403
    client.post('/api/auth/login', json={'user_id':'trusted'})
    assert client.post(path, json=versions | {'expected_content_version':2}).status_code == 409
    approved = client.post(path, json=versions).json()
    assert approved['status'] == 'in_transit' and approved['approval_mode'] == 'manual'
    assert approved['content_version'] == pending['content_version']
    assert approved['execution_version'] == pending['execution_version'] + 1
    assert client.post(path, json=versions).json()['id'] == approved['id']
    assert client.post(path, json=versions | {'expected_execution_version':99}).status_code == 409
    cancelled = client.post(f"/api/stock-transfers/{approved['id']}/cancel", json=dict(expected_content_version=1, expected_execution_version=approved['execution_version'],reason='另批登记',idempotency_key='cancel')).json()
    assert cancelled['status'] == 'cancelled'
    client.post('/api/auth/login', json={'user_id':'untrusted'})
    assert client.post('/api/stock-transfers', json=pending_payload).json()['id'] == pending['id']
    assert client.post('/api/stock-transfers', json=pending_payload | {'basis':'其他单据'}).status_code == 409
    pending2 = client.post('/api/stock-transfers', json=pending_payload | {'idempotency_key':'pending2'}).json()
    # Keep an existing trusted session while admin changes its authority.
    with TestClient(app) as actor:
        actor.post('/api/auth/login', json={'user_id':'trusted'})
        client.post('/api/auth/login', json={'user_id':'admin'})
        assert client.patch('/api/users/trusted', json={'role':'untrusted'}).status_code == 200
        target_path = f"/api/stock-transfers/{pending2['id']}/approve"
        assert actor.post(target_path, json=dict(expected_content_version=1,expected_execution_version=1)).status_code == 403
        assert client.patch('/api/users/trusted', json={'role':'trusted','active':False}).status_code == 200
        assert actor.post(target_path, json=dict(expected_content_version=1,expected_execution_version=1)).status_code in (401,403)
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
    data = dict(source_location_id=source,destination_location_id=target,action_kind='opening',effective_date='2026-10-13',basis='期初单',lines=[dict(sku_id=sku,quantity='2')],idempotency_key='invalid')
    for patch in ({'action_kind':'internal'}, {'action_kind':'adjustment_gain'}, {'destination_location_id':source}, {'fund_transfer_ids':['missing']}, {'lines':[dict(sku_id=sku,quantity='2'),dict(sku_id=sku,quantity='1')]}, *({'lines':[dict(sku_id=sku,quantity=q)]} for q in ['0','-1','1e2','1.1','1.0','１２','9007199254740992'])):
        assert client.post('/api/stock-transfers',json=data | patch).status_code in (400,404,409)
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = client.post('/api/stock-transfers',json=data).json()
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict(expected_content_version=1,expected_execution_version=1,reason='依据有误',idempotency_key='reject')
    path = f"/api/stock-transfers/{pending['id']}/reject"
    assert client.post(path,json=decision).json()['status'] == 'rejected'
    assert client.post(path,json=decision).status_code == 200
    assert client.post(path,json=decision | {'reason':'另一个原因'}).status_code == 409
    assert client.post(f"/api/stock-transfers/{pending['id']}/cancel",json=decision | {'expected_execution_version':2}).status_code == 409


def stock_setup(client):
    opening = client.post('/api/locations', json=dict(name='期初', kind='external', external_kind='opening')).json()['id']
    a, b = [client.post('/api/locations', json=dict(name=name)).json()['id'] for name in ('A','B')]
    skus = [client.post('/api/skus', json=dict(name=name,unit='本')).json()['id'] for name in ('书','册')]
    return opening, a, b, skus


def stock_plan(client, source, target, skus, quantities, key, action='internal'):
    response = client.post('/api/stock-transfers', json=dict(source_location_id=source,destination_location_id=target,action_kind=action,effective_date='2026-10-13',basis='核对单',lines=[dict(sku_id=s,quantity=q) for s,q in zip(skus,quantities)],idempotency_key=key))
    assert response.status_code == 201, response.text
    return response.json()


def completion_data(item, key):
    return dict(expected_content_version=item['content_version'],expected_execution_version=item['execution_version'],effective_date='2026-10-13',basis='实物核对',idempotency_key=key)


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
    assert complete(client,first,'batch1-complete').status_code == 200
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
    data['observations'] = [dict(line_id=item['lines'][0]['id'],observed_quantity='0',basis='尚待复核')]
    assert client.post(f"/api/stock-transfers/{item['id']}/completion",json=data | {'observations':[dict(line_id=item['lines'][0]['id'],observed_quantity='1.1',basis='核对')]}).status_code == 400
    pending = client.post(f"/api/stock-transfers/{item['id']}/completion",json=data).json()
    assert all(q == '0' for q in balances(client).values())
    confirmation = pending['confirmations'][0]
    decision = dict(expected_content_version=1,expected_execution_version=pending['execution_version'],idempotency_key='decision')
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path,json=decision).status_code == 403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert client.post(path,json=decision | {'expected_execution_version':2}).status_code == 409
    assert client.post(path.replace('/approve','/reject'),json=decision | {'reason':'重新核对'}).json()['status'] == 'in_transit'
    current = client.get(f"/api/stock-transfers/{item['id']}").json()
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = complete(client,current,'ordinary2').json()
    confirmation = pending['confirmations'][-1]
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict(expected_content_version=1,expected_execution_version=pending['execution_version'],idempotency_key='approve2')
    path = f"/api/stock-confirmations/{confirmation['id']}/approve"
    assert client.post(path,json=decision).json()['status'] == 'completed'
    assert client.post(path,json=decision).status_code == 200
    assert balances(client)[a,skus[0]] == '100'
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    assert complete(client,current,'ordinary2').status_code == 200
    assert client.post(f"/api/stock-transfers/{item['id']}/completion",json=completion_data(current,'ordinary2') | {'basis':'不同'}).status_code == 409
    client.post('/api/auth/login',json={'user_id':'trusted'})
    other = stock_plan(client,a,b,skus,['1','1'],'cancelled')
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending = complete(client,other,'cancel-request').json()
    client.post('/api/auth/login',json={'user_id':'trusted'})
    decision = dict(expected_content_version=1,expected_execution_version=pending['execution_version'],idempotency_key='cancel')
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
    assert complete(client,item,'rollback').status_code == 200
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


def difference(client,item,location,observed,key):
    payload = dict(line_id=item['lines'][0]['id'],location_id=location,observed_quantity=observed,comparison_at='2026-10-13T12:00:00+08:00',basis='本次转移实物核对',idempotency_key=key)
    response = client.post(f"/api/stock-transfers/{item['id']}/differences",json=payload)
    assert response.status_code == 201,response.text
    return response.json(),payload


def test_transfer_loss_difference_adjustments_and_custody(client):
    opening,a,b,skus = stock_setup(client)
    loss = client.post('/api/locations',json=dict(name='盘亏',kind='external',external_kind='adjustment_loss')).json()['id']
    gain = client.post('/api/locations',json=dict(name='盘盈',kind='external',external_kind='adjustment_gain')).json()['id']
    incoming = stock_plan(client,opening,a,skus[:1],['100'],'opening','opening')
    assert complete(client,incoming,'open').status_code == 200
    plan = stock_plan(client,a,b,skus[:1],['30'],'transfer')
    assert client.post(f"/api/stock-transfers/{plan['id']}/differences",json=dict(line_id=plan['lines'][0]['id'],location_id=b,observed_quantity='28',comparison_at='2026-10-13T12:00:00Z',basis='核对',idempotency_key='early')).status_code == 409
    finished = complete(client,plan,'transfer-complete').json()
    d,payload = difference(client,finished,b,'28','loss')
    assert d['delta'] == '-2' and d['status'] == 'unresolved'
    path = f"/api/stock-transfers/{finished['id']}/differences"
    assert client.post(path,json=payload).json()['id'] == d['id']
    assert client.post(path,json=payload | {'idempotency_key':'duplicate'}).status_code == 409
    assert client.post(path,json=payload | {'idempotency_key':'outside','location_id':opening}).status_code == 400
    adjustment_path = f"/api/stock-differences/{d['id']}/adjustment"
    adjustment_data = dict(external_location_id=loss,effective_date='2026-10-13',basis='核对盘亏',idempotency_key='adjust')
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    assert client.post(path,json=payload | {'idempotency_key':'unauthorized'}).status_code == 403
    assert client.post(adjustment_path,json=adjustment_data).status_code == 403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert client.post(adjustment_path,json=adjustment_data | {'external_location_id':gain}).status_code == 400
    adjustment = client.post(adjustment_path,json=adjustment_data).json()
    assert adjustment['status'] == 'in_transit' and adjustment['lines'][0]['quantity'] == '2'
    assert balances(client)[b,skus[0]] == '30'
    assert client.post(adjustment_path,json=adjustment_data).json()['id'] == adjustment['id']
    assert client.post(adjustment_path,json=adjustment_data | {'idempotency_key':'again'}).status_code == 409
    cancel = dict(expected_content_version=1,expected_execution_version=adjustment['execution_version'],reason='重新核对依据',idempotency_key='cancel-adjustment')
    assert client.post(f"/api/stock-transfers/{adjustment['id']}/cancel",json=cancel).status_code == 200
    adjustment = client.post(adjustment_path,json=adjustment_data | {'idempotency_key':'retry'}).json()
    assert complete(client,adjustment,'adjustment-complete').status_code == 200
    assert complete(client,adjustment,'adjustment-complete').status_code == 200
    inventory = client.get('/api/inventory',params={'sku_id':skus[0]}).json()
    assert balances(client)[a,skus[0]] == '70' and balances(client)[b,skus[0]] == '28'
    assert inventory['totals'][0]['quantity'] == '98'
    row = next(q for q in inventory['quantities'] if q['location_id'] == b)
    assert row['differences'][0]['status'] == 'resolved'
    assert client.post(adjustment_path,json=adjustment_data | {'idempotency_key':'completed-again'}).status_code == 409
    assert client.get('/api/stock-differences',params={'location_id':b}).json()[0]['id'] == d['id']
    members = [client.post('/api/members',json={'name':name}).json() for name in ('旧保管人','新保管人')]
    for member in members:
        assert client.post(f'/api/locations/{b}/custody',json={'member_id':member['id']}).status_code == 200
        current = client.get('/api/inventory',params={'member_id':member['id'],'sku_id':skus[0]}).json()
        assert current['totals'][0]['quantity'] == '28' and current['quantities'][0]['member_name'] == member['name']
    assert client.get('/api/inventory',params={'member_id':members[0]['id']}).json()['quantities'] == []
    moves = client.get('/api/stock-moves').json()
    assert next(m for m in moves if m['stock_transfer_id'] == finished['id'])['executor_id'] == 'trusted'


def test_under_shipped_independent_endpoint_differences(client):
    opening,a,b,skus = stock_setup(client)
    boundaries = {kind:client.post('/api/locations',json=dict(name=kind,kind='external',external_kind=kind)).json()['id'] for kind in ('adjustment_gain','adjustment_loss')}
    assert complete(client,stock_plan(client,opening,a,skus[:1],['100'],'opening','opening'),'open').status_code == 200
    original = complete(client,stock_plan(client,a,b,skus[:1],['30'],'move'),'move-complete').json()
    for location,key,kind in ((a,'source','adjustment_gain'),(b,'destination','adjustment_loss')):
        d,_ = difference(client,original,location,'28',key)
        assert d['delta'] == ('2' if location == a else '-2')
        adjustment = client.post(f"/api/stock-differences/{d['id']}/adjustment",json=dict(external_location_id=boundaries[kind],effective_date='2026-10-13',basis='少发两本仍在来源',idempotency_key=key)).json()
        assert complete(client,adjustment,key+'-complete').status_code == 200
    assert balances(client)[a,skus[0]] == '72' and balances(client)[b,skus[0]] == '28'
    assert client.get('/api/inventory',params={'sku_id':skus[0]}).json()['totals'][0]['quantity'] == '100'


def test_stock_fund_references_do_not_change_money(client):
    from backend.tests.test_member_claims import member,claim_payload,repayment_payload
    m = member(client)
    claim = client.post('/api/member-claims',json=claim_payload(m,'fund_pool',confirm=True)).json()
    assert claim['confirmed_minor'] == 100000
    repayment = client.post('/api/repayments',json=repayment_payload(client,m,'100','repayment')).json()
    baseline = (client.get('/api/funds/summary').json(),client.get(f"/api/members/{m['id']}").json(),client.get(f"/api/member-claims/{claim['id']}").json(),client.get('/api/repayments').json())
    source = client.post('/api/locations',json=dict(name='供应商',kind='external',external_kind='supplier')).json()['id']
    target = client.post('/api/locations',json=dict(name='仓库')).json()['id']
    sku = client.post('/api/skus',json=dict(name='书',unit='本')).json()['id']
    receipts = [stock_plan(client,source,target,[sku],['10'],f'receipt{i}','arrival') for i in range(2)]
    for i,item in enumerate(receipts):
        assert complete(client,item,f'complete{i}').status_code == 200
        path = f"/api/stock-transfers/{item['id']}/fund-references"
        data = dict(fund_transfer_id=claim['id'],idempotency_key=f'reference{i}')
        client.post('/api/auth/login',json={'user_id':'untrusted'})
        assert client.post(path,json=data).status_code == 403
        client.post('/api/auth/login',json={'user_id':'trusted'})
        linked = client.post(path,json=data).json()
        assert linked['fund_references'][0]['business_type'] == 'member_claim'
        assert linked['fund_references'][0]['member_id'] == m['id'] and linked['fund_references'][0]['status'] == 'posted'
        assert client.post(path,json=data).status_code == 200
        assert len(client.post(path,json=data | {'idempotency_key':f'duplicate{i}'}).json()['fund_references']) == 1
        assert client.post(path,json=data | {'idempotency_key':f'missing{i}','fund_transfer_id':'missing'}).status_code == 404
    assert (client.get('/api/funds/summary').json(),client.get(f"/api/members/{m['id']}").json(),client.get(f"/api/member-claims/{claim['id']}").json(),client.get('/api/repayments').json()) == baseline
    # Reverse the matched repayment first, then claim; stock links survive both money facts.
    assert client.post(f"/api/transfers/{repayment['id']}/reverse",json=dict(reason='退回偿还',idempotency_key='reverse-repayment')).status_code == 201
    assert client.post(f"/api/transfers/{claim['id']}/reverse",json=dict(reason='冲销垫付',idempotency_key='reverse-claim')).status_code == 201
    assert all(client.get(f"/api/stock-transfers/{item['id']}").json()['fund_references'][0]['status'] == 'reversed' for item in receipts)
    assert balances(client)[target,sku] == '20'
