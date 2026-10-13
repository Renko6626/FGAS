"""Real stock submission/approval paths; isolated PostgreSQL fixture only."""
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.entrypoints.http import app
from backend.infrastructure.database import Session
from backend.infrastructure.models import StockTransfer, StockTransferLine, JournalLine


def test_stock_submission_approval_and_retry(client):
    source = client.post('/api/locations', json=dict(name='商家', kind='external', external_kind='supplier')).json()['id']
    target = client.post('/api/locations', json=dict(name='仓库')).json()['id']
    skus = [client.post('/api/skus', json=dict(name=name, unit=unit, quantity_scale=scale)).json()['id'] for name, unit, scale in [('书','本',0),('材料','千克',3)]]
    payload = dict(source_location_id=source, destination_location_id=target, action_kind='arrival', effective_date='2026-10-13', basis='到货单 A', source_reference='receipt:A', lines=[dict(sku_id=skus[0], quantity='2'),dict(sku_id=skus[1],quantity='1.250')], idempotency_key='trusted')
    trusted = client.post('/api/stock-transfers', json=payload)
    assert trusted.status_code == 201
    trusted = trusted.json()
    assert trusted['status'] == 'in_transit' and trusted['approval_mode'] == 'automatic'
    assert {line['sku_id']: line['quantity'] for line in trusted['lines']} == {skus[0]:'2',skus[1]:'1.250'}
    assert trusted['approval_snapshot']['lines'] == trusted['lines']
    assert client.patch(f'/api/skus/{skus[0]}', json={'unit':'套'}).status_code == 409
    assert client.patch(f'/api/skus/{skus[1]}', json={'quantity_scale':2}).status_code == 409
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
    for patch in ({'action_kind':'internal'}, {'action_kind':'adjustment_gain'}, {'destination_location_id':source}, {'fund_transfer_ids':['missing']}, {'lines':[dict(sku_id=sku,quantity='2'),dict(sku_id=sku,quantity='1')]}, *({'lines':[dict(sku_id=sku,quantity=q)]} for q in ['0','-1','1e2','1.1','9007199254740992'])):
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
