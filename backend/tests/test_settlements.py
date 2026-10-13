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
    assert len(client.get('/api/transfers').json())==5
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
    assert len(client.get('/api/transfers').json())==4

def test_invalid_matches_rollback_payment_and_permission(client):
    account=private(client);other=private(client,'另一账户')
    item=transfer(client,account,'expense','100').json()
    before=client.get('/api/transfers').json()
    assert pay(client,'fund_pool',account,'101',[(item['id'],'101')]).status_code==400
    assert pay(client,'fund_pool',other,'100',[(item['id'],'100')]).status_code==400
    assert pay(client,'fund_pool',account,'50',[(item['id'],'100')]).status_code==400
    assert client.get('/api/transfers').json()==before
    client.post('/api/auth/login',json={'user_id':'untrusted'})
    pending=transfer(client,account,'expense','20').json()
    assert pending['status']=='pending'
    assert pay(client,'fund_pool',account,'20',[(item['id'],'20')]).status_code==403
    client.post('/api/auth/login',json={'user_id':'trusted'})
    assert pay(client,'fund_pool',account,'20',[(pending['id'],'20')]).status_code==409
    assert len(client.get('/api/transfers').json())==2

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
