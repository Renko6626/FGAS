"""Member claim behavior against the shared dedicated PostgreSQL fixture."""
from backend.tests.test_funds import transfer


def member(client):
    response = client.post('/api/members', json={'name': '代录成员'})
    assert response.status_code == 201
    return response.json()


def claim_payload(m, destination='expense', key='claim', confirm=False):
    return dict(member_id=m['id'], destination_account_id=destination, amount='1000',
                effective_date='2026-10-13', basis='付款凭据', confirm_now=confirm, idempotency_key=key)


def test_claim_confirmation_retry_and_reversal(client):
    m = member(client)
    payload = claim_payload(m)
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.post('/api/member-claims', json=payload).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    response = client.post('/api/member-claims', json=payload)
    assert response.status_code == 201
    pending = response.json()
    identifier = pending['id']
    assert pending['declared_minor'] == 100000 and pending['confirmed_minor'] is None
    assert pending['transfer']['journal_lines'] == []
    assert pending['outstanding_minor'] == 0
    assert client.post(f'/api/transfers/{identifier}/approve', json={'expected_version': pending['version']}).status_code == 409
    confirmation = dict(expected_version=pending['version'], confirmed_amount='800', confirmation_reason='实际认可金额')
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.post(f'/api/member-claims/{identifier}/confirm', json=confirmation).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.post(f'/api/member-claims/{identifier}/confirm', json={**confirmation, 'confirmation_reason': ''}).status_code == 400
    confirmed_response = client.post(f'/api/member-claims/{identifier}/confirm', json=confirmation)
    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()
    assert confirmed['confirmed_minor'] == confirmed['outstanding_minor'] == 80000
    assert confirmed['confirmation_reason'] == '实际认可金额' and confirmed['confirmed_at']
    assert confirmed['transfer']['amount_minor'] == 80000
    assert confirmed['transfer']['business'] == dict(kind='member_claim', id=identifier, member_id=m['id'])
    assert client.get('/api/funds/summary').json()['total_minor'] == 0
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 80000
    retry = client.post('/api/member-claims', json=payload).json()
    assert retry['id'] == identifier and retry['confirmed_minor'] == 80000
    assert len(retry['transfer']['journal_lines']) == 2
    assert client.post('/api/member-claims', json={**payload, 'basis': '更改依据'}).status_code == 409
    assert client.post(f'/api/member-claims/{identifier}/confirm', json=confirmation).status_code == 409
    reverse_payload = dict(reason='重复登记', idempotency_key='claim-reverse')
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.post(f'/api/transfers/{identifier}/reverse', json=reverse_payload).status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    response = client.post(f'/api/transfers/{identifier}/reverse', json=reverse_payload)
    assert response.status_code == 201
    reversal = response.json()
    assert reversal['business']['id'] == identifier
    assert client.get(f'/api/member-claims/{identifier}').json()['outstanding_minor'] == 0
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 0
    assert client.post(f'/api/transfers/{identifier}/reverse', json=reverse_payload).json()['id'] == reversal['id']
    assert client.post(f"/api/transfers/{reversal['id']}/reverse", json=dict(reason='重新恢复', idempotency_key='reverse-again')).status_code == 409


def test_claim_destination_and_unmarked_member_transfer(client):
    m = member(client)
    response = client.post('/api/member-claims', json=claim_payload(m, 'fund_pool', confirm=True))
    assert response.status_code == 201
    claim = response.json()
    assert claim['outstanding_minor'] == 100000
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    ordinary = transfer(client, 'fund_pool', m['account_id'], '100', 'ordinary-member')
    assert ordinary.status_code == 201 and ordinary.json()['business'] is None
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 90000
    current = client.get(f"/api/member-claims/{claim['id']}").json()
    assert current['outstanding_minor'] == 100000 and current['repaid_minor'] == 0
    other = client.post('/api/member-claims', json=claim_payload(m, 'opening', key='non-expense', confirm=True))
    assert other.status_code == 201 and other.json()['transfer']['destination_account_id'] == 'opening'
    assert len(client.get('/api/member-claims', params={'member_id': m['id'], 'status': 'posted'}).json()) == 2


def test_claim_reversal_refreshes_preloaded_pending_amount(client):
    from backend.application import funds
    from backend.infrastructure import store
    from backend.infrastructure.database import Session

    m = member(client)
    pending = client.post('/api/member-claims', json=claim_payload(m)).json()
    identifier = pending['id']
    # Two real transactions: reversal's identity map retains the pre-confirmation
    # amount while the HTTP confirmation commits a different recognized amount.
    with Session.begin() as db:
        stale_original = store.get_transfer(db, identifier)
        user = store.get_user(db, 'trusted')
        assert stale_original.status == 'pending' and stale_original.amount_minor == 100000
        response = client.post(f'/api/member-claims/{identifier}/confirm', json=dict(
            expected_version=pending['version'], confirmed_amount='800', confirmation_reason='部分认可'))
        assert response.status_code == 200
        assert stale_original.amount_minor == 100000
        reversal = funds.reverse(db, user, identifier, '撤回垫付', 'stale-reversal')
        assert reversal['amount_minor'] == 80000
        assert sum(line['debit_minor'] for line in reversal['journal_lines']) == 80000
        assert stale_original.amount_minor == 80000 and stale_original.status == 'reversed'
    assert client.get(f'/api/member-claims/{identifier}').json()['outstanding_minor'] == 0
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 0
    retry = client.post(f'/api/transfers/{identifier}/reverse', json=dict(
        reason='撤回垫付', idempotency_key='stale-reversal'))
    assert retry.status_code == 201 and retry.json()['id'] == reversal['id']
