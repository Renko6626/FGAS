"""Dashboard totals use real postings, rather than transfer creation dates."""
from backend.tests.conftest import seed_code
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from backend.infrastructure.database import Session
from backend.infrastructure.models import Transfer, StockMove


def fund(client, source, destination, amount):
    response = client.post('/api/transfers', json=dict(
        source_account_code=source, destination_account_code=destination,
        amount=amount, effective_date='2020-01-01'))
    assert response.status_code == 201, response.text
    return response.json()


def test_dashboard_empty_and_authenticated(client):
    response = client.get('/api/dashboard')
    assert response.status_code == 200
    data = response.json()
    assert data['funds'] == dict(total_minor=0, incoming_minor=0, outgoing_minor=0, net_minor=0, recent=[])
    assert data['stock'] == dict(skus=[], recent=[])
    assert data['operations'] == dict(all=[], funds=[], stock=[])
    client.post('/api/auth/logout')
    assert client.get('/api/dashboard').status_code == 401


def test_dashboard_fund_postings_window_and_reversal(client):
    extra = client.post('/api/accounts', json={'name': '备用公账', 'kind': 'public'}).json()['code']
    private = client.post('/api/accounts', json={'name': '个人往来', 'kind': 'private'}).json()['code']
    opening = fund(client, seed_code('opening'), seed_code('fund_pool'), '200')
    old_expense = fund(client, seed_code('fund_pool'), seed_code('expense'), '20')
    with Session.begin() as db:
        db.execute(update(Transfer).where(Transfer.code.in_([opening['code'], old_expense['code']])).values(
            posted_at=datetime.now(timezone.utc) - timedelta(days=8)))
    fund(client, seed_code('fund_pool'), extra, '30')
    fund(client, seed_code('opening'), private, '12')  # Private money does not enter the public total.
    expense = fund(client, seed_code('fund_pool'), seed_code('expense'), '50')
    reversal = client.post(f"/api/transfers/{old_expense['code']}/reverse", json={'reason': '更正'}).json()
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    pending = fund(client, seed_code('opening'), seed_code('fund_pool'), '999')
    data = client.get('/api/dashboard').json()
    assert data['funds']['total_minor'] == 15000
    assert data['funds']['incoming_minor'] == 2000
    assert data['funds']['outgoing_minor'] == 5000
    assert data['funds']['net_minor'] == -3000
    assert [row['code'] for row in data['funds']['recent']][:2] == [reversal['code'], expense['code']]
    assert [row['delta_minor'] for row in data['funds']['recent']][:2] == [2000, -5000]
    assert data['counts']['pendingFunds'] == 1
    assert data['operations']['all'][0]['code'] == pending['code']
    assert data['operations']['all'][0]['status'] == 'pending'


def test_dashboard_owned_stock_and_mixed_activity(client):
    external = client.post('/api/stock-accounts', json={'name': '商家', 'kind': 'external'}).json()['code']
    public = client.post('/api/stock-accounts', json={'name': '社团仓库', 'kind': 'internal'}).json()['code']
    private = client.post('/api/stock-accounts', json={'name': '成员代管', 'kind': 'internal'}).json()['code']
    book = client.post('/api/skus', json={'code': 'BOOK-01', 'name': '甲刊物', 'unit': '本'}).json()['code']
    card = client.post('/api/skus', json={'code': 'CARD-01', 'name': '乙卡片', 'unit': '张'}).json()['code']
    codes = {book: 'BOOK-01', card: 'CARD-01'}

    def stock(source, target, quantities, completed=True):
        response = client.post('/api/stock-transfers', json=dict(
            source_account_code=source, destination_account_code=target,
            effective_date='2020-01-01', description='货物测试',
            lines=[dict(sku_code=codes[sku], quantity=str(q)) for sku, q in quantities]))
        assert response.status_code == 201, response.text
        item = response.json()
        if completed:
            result = client.post(f"/api/stock-transfers/{item['code']}/completion", json={'effective_date': '2020-01-01'})
            assert result.status_code == 200, result.text
        return item

    stock(external, public, [(book, 100), (card, 25)])
    with Session.begin() as db:
        db.execute(update(StockMove).values(created_at=datetime.now(timezone.utc) - timedelta(days=8)))
    internal = stock(public, private, [(book, 30)])
    incoming = stock(external, private, [(book, 10), (card, 5)])
    outgoing = stock(private, external, [(book, 4)])
    stock(public, private, [(card, 1)])  # Internal moves do not reprioritize total-stock changes.
    transit = stock(external, public, [(book, 999)], completed=False)
    money = fund(client, seed_code('opening'), seed_code('fund_pool'), '1')
    data = client.get('/api/dashboard').json()
    rows = {row['sku_code']: row for row in data['stock']['skus']}
    assert [row['sku_code'] for row in data['stock']['skus']] == [book, card]
    assert {row['sku_code']: row['sku_code'] for row in data['stock']['skus']} == codes
    assert (rows[book]['quantity'], rows[book]['net_quantity'], rows[book]['incoming_quantity'], rows[book]['outgoing_quantity']) == ('106', '6', '10', '4')
    assert (rows[card]['quantity'], rows[card]['net_quantity'], rows[card]['unit']) == ('30', '5', '张')
    assert [row['code'] for row in data['stock']['recent']][:2] == [outgoing['code'], incoming['code']]
    assert internal['code'] not in [row['code'] for row in data['stock']['recent']]
    assert data['stock']['recent'][1]['lines'][0]['delta_quantity'] in ('10', '5')
    assert {line['sku_code'] for line in data['stock']['recent'][1]['lines']} == {'BOOK-01', 'CARD-01'}
    assert data['counts']['inTransit'] == 1
    assert data['operations']['all'][0]['code'] == money['code']
    assert data['operations']['stock'][0]['code'] == transit['code']
    assert data['operations']['stock'][0]['lines'][0]['quantity'] == '999'
    assert data['operations']['stock'][0]['lines'][0]['sku_code'] == 'BOOK-01'
    assert data['operations']['stock'][0]['actor_name'] == '受信任成员'
