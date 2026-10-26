"""Settlement behavior over real transfers and journal lines."""
from backend.tests.test_funds import transfer

def private(client,name='小王'):
    response=client.post('/api/accounts',json={'name':name,'kind':'private'})
    assert response.status_code==201,response.text
    return response.json()['id']

def overview(client,account):
    response=client.get(f'/api/accounts/{account}/settlement-overview')
    assert response.status_code==200,response.text
    return response.json()

def pay(client,source,destination,amount,allocations):
    return client.post('/api/settlements',json={'transfer':{'source_account_id':source,'destination_account_id':destination,'amount':amount,'effective_date':'2026-10-14'},'allocations':[{'item_transfer_id':i,'amount':a} for i,a in allocations]})

def test_expenses_partial_and_multiple_settlements(client):
    account=private(client)
    items=[transfer(client,account,'expense',a).json() for a in ('300','80','120')]
    assert overview(client,account)['account']['balance_minor']==-50000
    payment=pay(client,'fund_pool',account,'400',[(items[0]['id'],'300'),(items[1]['id'],'80'),(items[2]['id'],'20')])
    assert payment.status_code==201,payment.text
    current=overview(client,account)
    assert current['account']['balance_minor']==-10000
    assert {i['transfer']['id']:i['outstanding_minor'] for i in current['expenses']}=={items[0]['id']:0,items[1]['id']:0,items[2]['id']:10000}
    assert pay(client,'fund_pool',account,'100',[(items[2]['id'],'100')]).status_code==201
    current=overview(client,account)
    assert current['account']['balance_minor']==0
    assert all(i['outstanding_minor']==0 for i in current['expenses'])
    assert len(client.get('/api/transfers').json()['items'])==5
    assert client.get('/api/funds/summary').json()['total_minor']==-50000

def test_receipts_and_existing_payment_matching(client):
    account=private(client)
    items=[transfer(client,'income',account,a).json() for a in ('200','300')]
    payment=transfer(client,account,'fund_pool','400').json()
    response=client.post(f"/api/transfers/{payment['id']}/settlement-matches",json={'allocations':[{'item_transfer_id':items[0]['id'],'amount':'200'},{'item_transfer_id':items[1]['id'],'amount':'200'}]})
    assert response.status_code==201,response.text
    current=overview(client,account)
    assert current['account']['balance_minor']==10000
    assert {i['transfer']['id']:i['outstanding_minor'] for i in current['receipts']}=={items[0]['id']:0,items[1]['id']:10000}
    assert pay(client,account,'fund_pool','100',[(items[1]['id'],'100')]).status_code==201
    assert overview(client,account)['account']['balance_minor']==0
    assert client.get('/api/funds/summary').json()['total_minor']==50000
    assert len(client.get('/api/transfers').json()['items'])==4

def test_invalid_matches_rollback_payment_and_permission(client):
    account=private(client);other=private(client,'另一账户')
    item=transfer(client,account,'expense','100').json()
    before=client.get('/api/transfers').json()['items']
    assert pay(client,'fund_pool',account,'101',[(item['id'],'101')]).status_code==400
    assert pay(client,'fund_pool',other,'100',[(item['id'],'100')]).status_code==400
    assert pay(client,'fund_pool',account,'50',[(item['id'],'100')]).status_code==400
    assert client.get('/api/transfers').json()['items']==before
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending=transfer(client,account,'expense','20').json()
    assert pending['status']=='pending'
    assert pay(client,'fund_pool',account,'20',[(item['id'],'20')]).status_code==403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert pay(client,'fund_pool',account,'20',[(pending['id'],'20')]).status_code==409
    assert len(client.get('/api/transfers').json()['items'])==2

def test_payment_and_item_reversal_invalidate_matches(client):
    account=private(client)
    item=transfer(client,account,'expense','100').json()
    payment=pay(client,'fund_pool',account,'60',[(item['id'],'60')]).json()['transfer']
    assert client.post(f"/api/transfers/{payment['id']}/reverse",json={'reason':'付款录错'}).status_code==201
    current=overview(client,account)
    assert current['expenses'][0]['outstanding_minor']==10000
    assert not current['settlements'][0]['matches'][0]['effective']
    second=pay(client,'fund_pool',account,'100',[(item['id'],'100')]).json()['transfer']
    assert client.post(f"/api/transfers/{item['id']}/reverse",json={'reason':'原支出录错'}).status_code==201
    current=overview(client,account)
    valid_payment=next(p for p in current['settlements'] if p['transfer']['id']==second['id'])
    assert valid_payment['unmatched_minor']==10000
    assert not valid_payment['matches'][0]['effective']
    assert current['account']['balance_minor']==10000

def test_partial_payment_remainder_and_duplicate_match(client):
    account=private(client)
    first=transfer(client,account,'expense','100').json()
    second=transfer(client,account,'expense','100').json()
    payment=pay(client,'fund_pool',account,'150',[(first['id'],'100')]).json()['transfer']
    path=f"/api/transfers/{payment['id']}/settlement-matches"
    assert client.post(path,json={'allocations':[{'item_transfer_id':first['id'],'amount':'1'}]}).status_code==400
    assert client.post(path,json={'allocations':[{'item_transfer_id':second['id'],'amount':'51'}]}).status_code==400
    assert client.post(path,json={'allocations':[{'item_transfer_id':second['id'],'amount':'50'}]}).status_code==201
    current=overview(client,account)
    assert current['settlements'][0]['matched_minor']==15000
    assert current['settlements'][0]['unmatched_minor']==0


def test_global_outstanding_filters_pagination_and_zero_balance(client):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from backend.infrastructure.database import Session
    from backend.infrastructure.models import Audit, JournalLine, SettlementMatch, Transfer

    first, second = private(client), private(client, '小李')
    expense = transfer(client, first, 'expense', '100').json()
    payment = transfer(client, 'fund_pool', first, '100').json()
    other_expense = transfer(client, second, 'expense', '200').json()
    other_payment = pay(client, 'fund_pool', second, '60', [(other_expense['id'], '40')])
    assert other_payment.status_code == 201
    other_payment = other_payment.json()['transfer']
    receipt = transfer(client, 'income', second, '30').json()
    returned = transfer(client, second, 'fund_pool', '10').json()
    closed = transfer(client, first, 'expense', '5').json()
    assert pay(client, 'fund_pool', first, '5', [(closed['id'], '5')]).status_code == 201
    assert transfer(client, 'opening', 'fund_pool', '3').status_code == 201
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert transfer(client, second, 'expense', '7').json()['status'] == 'pending'
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.patch(f'/api/accounts/{first}', json={'active': False}).status_code == 200
    with Session.begin() as db:
        db.get(Transfer, expense['id']).created_at = datetime.now(timezone.utc) - timedelta(days=45)

    def counts():
        with Session() as db:
            return tuple(db.scalar(select(func.count()).select_from(model))
                         for model in (Transfer, JournalLine, SettlementMatch, Audit))

    before = counts()
    response = client.get('/api/settlement-outstanding')
    assert response.status_code == 200, response.text
    data = response.json()
    expected = [returned['id'], receipt['id'], other_payment['id'], other_expense['id'], payment['id'], expense['id']]
    assert [row['transfer_id'] for row in data['items']] == expected
    assert data['total'] == 6 and data['snapshot_at']
    rows = {row['transfer_id']: row for row in data['items']}
    assert rows[expense['id']]['remaining_minor'] == rows[payment['id']]['remaining_minor'] == 10000
    assert rows[other_expense['id']]['remaining_minor'] == 16000
    assert rows[other_payment['id']]['matched_minor'] == 4000
    assert rows[other_payment['id']]['remaining_minor'] == 2000
    assert rows[receipt['id']]['direction'] == rows[returned['id']]['direction'] == 'receipt'
    assert overview(client, first)['account']['balance_minor'] == 0

    pages = [client.get('/api/settlement-outstanding', params={'page': page, 'limit': 2}).json()
             for page in (1, 2, 3, 4)]
    assert [row['transfer_id'] for page in pages for row in page['items']] == expected
    assert all(page['total'] == 6 for page in pages)
    filtered = client.get('/api/settlement-outstanding', params={
        'account_id': second, 'direction': 'expense', 'kind': 'payment',
    }).json()
    assert [row['transfer_id'] for row in filtered['items']] == [other_payment['id']]
    assert client.get('/api/settlement-outstanding', params={'account_id': 'missing'}).status_code == 404
    assert client.get('/api/settlement-outstanding', params={'account_id': 'fund_pool'}).status_code == 400
    assert client.get('/api/settlement-outstanding', params={'direction': 'invalid'}).status_code == 422
    assert client.get('/api/settlement-outstanding', params={'limit': 0}).status_code == 422
    assert counts() == before


def test_global_outstanding_ignores_reversed_matches(client):
    account = private(client)
    item = transfer(client, account, 'expense', '100').json()
    payment = pay(client, 'fund_pool', account, '60', [(item['id'], '60')]).json()['transfer']
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_id'], row['remaining_minor']) for row in response['items']] == [(item['id'], 4000)]

    assert client.post(f"/api/transfers/{payment['id']}/reverse", json={'reason': '付款录错'}).status_code == 201
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_id'], row['remaining_minor']) for row in response['items']] == [(item['id'], 10000)]
    replacement = pay(client, 'fund_pool', account, '100', [(item['id'], '100')]).json()['transfer']
    assert client.get('/api/settlement-outstanding').json()['items'] == []
    assert client.post(f"/api/transfers/{item['id']}/reverse", json={'reason': '原支出录错'}).status_code == 201
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_id'], row['kind'], row['remaining_minor']) for row in response['items']] == [
        (replacement['id'], 'payment', 10000),
    ]
