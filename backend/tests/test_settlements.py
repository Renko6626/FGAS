"""Settlement behavior over real transfers and journal lines."""
from backend.tests.conftest import seed_code
from backend.application.directory_views import by_code
from backend.tests.test_funds import transfer

def private(client,name='小王'):
    response=client.post('/api/accounts',json={'name':name,'kind':'private'})
    assert response.status_code==201,response.text
    return response.json()['code']

def overview(client,account):
    response=client.get(f'/api/accounts/{account}/settlement-overview')
    assert response.status_code==200,response.text
    return response.json()

def pay(client,source,destination,amount,allocations):
    return client.post('/api/settlements',json={'transfer':{'source_account_code':source,'destination_account_code':destination,'amount':amount,'effective_date':'2026-10-14'},'allocations':[{'item_transfer_code':i,'amount':a} for i,a in allocations]})

def test_expenses_partial_and_multiple_settlements(client):
    account=private(client)
    items=[transfer(client,account,seed_code('expense'),a).json() for a in ('300','80','120')]
    assert overview(client,account)['account']['balance_minor']==-50000
    payment=pay(client,seed_code('fund_pool'),account,'400',[(items[0]['code'],'300'),(items[1]['code'],'80'),(items[2]['code'],'20')])
    assert payment.status_code==201,payment.text
    current=overview(client,account)
    assert current['account']['balance_minor']==-10000
    assert {i['transfer']['code']:i['outstanding_minor'] for i in current['expenses']}=={items[0]['code']:0,items[1]['code']:0,items[2]['code']:10000}
    assert pay(client,seed_code('fund_pool'),account,'100',[(items[2]['code'],'100')]).status_code==201
    current=overview(client,account)
    assert current['account']['balance_minor']==0
    assert all(i['outstanding_minor']==0 for i in current['expenses'])
    assert len(client.get('/api/transfers').json()['items'])==5
    assert client.get('/api/funds/summary').json()['total_minor']==-50000

def test_receipts_and_existing_payment_matching(client):
    account=private(client)
    items=[transfer(client,seed_code('income'),account,a).json() for a in ('200','300')]
    payment=transfer(client,account,seed_code('fund_pool'),'400').json()
    response=client.post(f"/api/transfers/{payment['code']}/settlement-matches",json={'allocations':[{'item_transfer_code':items[0]['code'],'amount':'200'},{'item_transfer_code':items[1]['code'],'amount':'200'}]})
    assert response.status_code==201,response.text
    current=overview(client,account)
    assert current['account']['balance_minor']==10000
    assert {i['transfer']['code']:i['outstanding_minor'] for i in current['receipts']}=={items[0]['code']:0,items[1]['code']:10000}
    assert pay(client,account,seed_code('fund_pool'),'100',[(items[1]['code'],'100')]).status_code==201
    assert overview(client,account)['account']['balance_minor']==0
    assert client.get('/api/funds/summary').json()['total_minor']==50000
    assert len(client.get('/api/transfers').json()['items'])==4

def test_invalid_matches_rollback_payment_and_permission(client):
    account=private(client);other=private(client,'另一账户')
    item=transfer(client,account,seed_code('expense'),'100').json()
    before=client.get('/api/transfers').json()['items']
    assert pay(client,seed_code('fund_pool'),account,'101',[(item['code'],'101')]).status_code==400
    assert pay(client,seed_code('fund_pool'),other,'100',[(item['code'],'100')]).status_code==400
    assert pay(client,seed_code('fund_pool'),account,'50',[(item['code'],'100')]).status_code==400
    assert client.get('/api/transfers').json()['items']==before
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending=transfer(client,account,seed_code('expense'),'20').json()
    assert pending['status']=='pending'
    assert pay(client,seed_code('fund_pool'),account,'20',[(item['code'],'20')]).status_code==403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert pay(client,seed_code('fund_pool'),account,'20',[(pending['code'],'20')]).status_code==409
    assert len(client.get('/api/transfers').json()['items'])==2

def test_payment_and_item_reversal_invalidate_matches(client):
    account=private(client)
    item=transfer(client,account,seed_code('expense'),'100').json()
    payment=pay(client,seed_code('fund_pool'),account,'60',[(item['code'],'60')]).json()['transfer']
    assert client.post(f"/api/transfers/{payment['code']}/reverse",json={'reason':'付款录错'}).status_code==201
    current=overview(client,account)
    assert current['expenses'][0]['outstanding_minor']==10000
    assert not current['settlements'][0]['matches'][0]['effective']
    second=pay(client,seed_code('fund_pool'),account,'100',[(item['code'],'100')]).json()['transfer']
    assert client.post(f"/api/transfers/{item['code']}/reverse",json={'reason':'原支出录错'}).status_code==201
    current=overview(client,account)
    valid_payment=next(p for p in current['settlements'] if p['transfer']['code']==second['code'])
    assert valid_payment['unmatched_minor']==10000
    assert not valid_payment['matches'][0]['effective']
    assert current['account']['balance_minor']==10000

def test_partial_payment_remainder_and_duplicate_match(client):
    account=private(client)
    first=transfer(client,account,seed_code('expense'),'100').json()
    second=transfer(client,account,seed_code('expense'),'100').json()
    payment=pay(client,seed_code('fund_pool'),account,'150',[(first['code'],'100')]).json()['transfer']
    path=f"/api/transfers/{payment['code']}/settlement-matches"
    assert client.post(path,json={'allocations':[{'item_transfer_code':first['code'],'amount':'1'}]}).status_code==400
    assert client.post(path,json={'allocations':[{'item_transfer_code':second['code'],'amount':'51'}]}).status_code==400
    assert client.post(path,json={'allocations':[{'item_transfer_code':second['code'],'amount':'50'}]}).status_code==201
    current=overview(client,account)
    assert current['settlements'][0]['matched_minor']==15000
    assert current['settlements'][0]['unmatched_minor']==0


def test_global_outstanding_filters_pagination_and_zero_balance(client):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func, select
    from backend.infrastructure.database import Session
    from backend.infrastructure.models import Audit, JournalLine, SettlementMatch, Transfer

    first, second = private(client), private(client, '小李')
    expense = transfer(client, first, seed_code('expense'), '100').json()
    payment = transfer(client, seed_code('fund_pool'), first, '100').json()
    other_expense = transfer(client, second, seed_code('expense'), '200').json()
    other_payment = pay(client, seed_code('fund_pool'), second, '60', [(other_expense['code'], '40')])
    assert other_payment.status_code == 201
    other_payment = other_payment.json()['transfer']
    receipt = transfer(client, seed_code('income'), second, '30').json()
    returned = transfer(client, second, seed_code('fund_pool'), '10').json()
    closed = transfer(client, first, seed_code('expense'), '5').json()
    assert pay(client, seed_code('fund_pool'), first, '5', [(closed['code'], '5')]).status_code == 201
    assert transfer(client, seed_code('opening'), seed_code('fund_pool'), '3').status_code == 201
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert transfer(client, second, seed_code('expense'), '7').json()['status'] == 'pending'
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.patch(f'/api/accounts/{first}', json={'active': False}).status_code == 200
    with Session.begin() as db:
        by_code(db, Transfer, expense['code']).created_at = datetime.now(timezone.utc) - timedelta(days=45)

    def counts():
        with Session() as db:
            return tuple(db.scalar(select(func.count()).select_from(model))
                         for model in (Transfer, JournalLine, SettlementMatch, Audit))

    before = counts()
    response = client.get('/api/settlement-outstanding')
    assert response.status_code == 200, response.text
    data = response.json()
    expected = [returned['code'], receipt['code'], other_payment['code'], other_expense['code'], payment['code'], expense['code']]
    assert [row['transfer_code'] for row in data['items']] == expected
    assert data['total'] == 6 and data['snapshot_at']
    rows = {row['transfer_code']: row for row in data['items']}
    assert rows[expense['code']]['remaining_minor'] == rows[payment['code']]['remaining_minor'] == 10000
    assert rows[other_expense['code']]['remaining_minor'] == 16000
    assert rows[other_payment['code']]['matched_minor'] == 4000
    assert rows[other_payment['code']]['remaining_minor'] == 2000
    assert rows[receipt['code']]['direction'] == rows[returned['code']]['direction'] == 'receipt'
    assert overview(client, first)['account']['balance_minor'] == 0

    pages = [client.get('/api/settlement-outstanding', params={'page': page, 'limit': 2}).json()
             for page in (1, 2, 3, 4)]
    assert [row['transfer_code'] for page in pages for row in page['items']] == expected
    assert all(page['total'] == 6 for page in pages)
    filtered = client.get('/api/settlement-outstanding', params={
        'account_code': second, 'direction': 'expense', 'kind': 'payment',
    }).json()
    assert [row['transfer_code'] for row in filtered['items']] == [other_payment['code']]
    assert client.get('/api/settlement-outstanding', params={'account_code': 'missing'}).status_code == 404
    assert client.get('/api/settlement-outstanding', params={'account_code': seed_code('fund_pool')}).status_code == 400
    assert client.get('/api/settlement-outstanding', params={'direction': 'invalid'}).status_code == 422
    assert client.get('/api/settlement-outstanding', params={'limit': 0}).status_code == 422
    assert counts() == before


def test_global_outstanding_ignores_reversed_matches(client):
    account = private(client)
    item = transfer(client, account, seed_code('expense'), '100').json()
    payment = pay(client, seed_code('fund_pool'), account, '60', [(item['code'], '60')]).json()['transfer']
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_code'], row['remaining_minor']) for row in response['items']] == [(item['code'], 4000)]

    assert client.post(f"/api/transfers/{payment['code']}/reverse", json={'reason': '付款录错'}).status_code == 201
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_code'], row['remaining_minor']) for row in response['items']] == [(item['code'], 10000)]
    replacement = pay(client, seed_code('fund_pool'), account, '100', [(item['code'], '100')]).json()['transfer']
    assert client.get('/api/settlement-outstanding').json()['items'] == []
    assert client.post(f"/api/transfers/{item['code']}/reverse", json={'reason': '原支出录错'}).status_code == 201
    response = client.get('/api/settlement-outstanding').json()
    assert [(row['transfer_code'], row['kind'], row['remaining_minor']) for row in response['items']] == [
        (replacement['code'], 'payment', 10000),
    ]
