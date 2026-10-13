"""Member claim behavior against the shared dedicated PostgreSQL fixture."""
from backend.tests.test_funds import transfer


def member(client):
    response = client.post('/api/members', json={'name': '代录成员'})
    assert response.status_code == 201
    return response.json()


def claim_payload(m, destination='expense', confirm=False):
    return dict(member_id=m['id'], destination_account_id=destination, amount='1000',
                effective_date='2026-10-13', basis='付款凭据', confirm_now=confirm)


def test_claim_confirmation_and_reversal(client):
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
    assert client.post(f'/api/member-claims/{identifier}/confirm', json=confirmation).status_code == 409
    reverse_payload = dict(reason='重复登记')
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
    assert client.post(f'/api/transfers/{identifier}/reverse', json=reverse_payload).status_code == 409
    assert client.post(f"/api/transfers/{reversal['id']}/reverse", json=dict(reason='重新恢复')).status_code == 409


def test_claim_destination_and_unmarked_member_transfer(client):
    m = member(client)
    response = client.post('/api/member-claims', json=claim_payload(m, 'fund_pool', confirm=True))
    assert response.status_code == 201
    claim = response.json()
    assert claim['outstanding_minor'] == 100000
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000
    initial_detail = client.get(f"/api/members/{m['id']}").json()
    assert initial_detail['outstanding_minor'] == initial_detail['confirmed_minor'] == 100000
    assert initial_detail['ledger_balance_minor'] == 100000
    assert initial_detail['pending_minor'] == initial_detail['repaid_minor'] == initial_detail['other_movements_minor'] == 0
    ordinary = transfer(client, 'fund_pool', m['account_id'], '100')
    assert ordinary.status_code == 201 and ordinary.json()['business'] is None
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 90000
    current = client.get(f"/api/member-claims/{claim['id']}").json()
    assert current['outstanding_minor'] == 100000 and current['repaid_minor'] == 0
    overview = client.get(f"/api/members/{m['id']}").json()
    assert overview['outstanding_minor'] == 100000
    assert overview['other_movements_minor'] == -10000
    assert overview['ledger_balance_minor'] == 90000
    assert [t['id'] for t in overview['other_transfers']] == [ordinary.json()['id']]
    other = client.post('/api/member-claims', json=claim_payload(m, 'opening', confirm=True))
    assert other.status_code == 201 and other.json()['transfer']['destination_account_id'] == 'opening'
    assert len(client.get('/api/member-claims', params={'member_id': m['id'], 'status': 'posted'}).json()) == 2
    b = member(client)
    marked = client.post('/api/member-claims', json=dict(
        claim_payload(m, b['account_id'], confirm=True), amount='50'))
    assert marked.status_code == 201
    a_detail = client.get(f"/api/members/{m['id']}").json()
    b_detail = client.get(f"/api/members/{b['id']}").json()
    assert a_detail['outstanding_minor'] == 205000 and a_detail['ledger_balance_minor'] == 195000
    assert a_detail['other_movements_minor'] == -10000
    assert b_detail['outstanding_minor'] == 0 and b_detail['other_movements_minor'] == -5000
    assert b_detail['ledger_balance_minor'] == -5000 and b_detail['claims'] == []
    assert [t['id'] for t in b_detail['other_transfers']] == [marked.json()['id']]



def test_claim_decisions_and_reversal_refresh_preloaded_pending_state(client):
    import pytest
    from backend.application import funds
    from backend.infrastructure import store
    from backend.infrastructure.database import Session
    from backend.kernel.accounting import DomainError

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
        reversal = funds.reverse(db, user, identifier, '撤回垫付')
        assert reversal['amount_minor'] == 80000
        assert sum(line['debit_minor'] for line in reversal['journal_lines']) == 80000
        assert stale_original.amount_minor == 80000 and stale_original.status == 'reversed'
    assert client.get(f'/api/member-claims/{identifier}').json()['outstanding_minor'] == 0
    accounts = client.get('/api/accounts').json()
    assert next(a for a in accounts if a['id'] == m['account_id'])['balance_minor'] == 0
    retry = client.post(f'/api/transfers/{identifier}/reverse', json=dict(
        reason='撤回垫付'))
    assert retry.status_code == 409

    # Both decisions start with a retained pending Transfer before a separate
    # transaction confirms the full amount, so no amount mismatch masks the race.
    for index, rejection in enumerate([None, '拒绝垫付']):
        decision_member = member(client)
        pending = client.post('/api/member-claims', json=claim_payload(decision_member)).json()
        identifier = pending['id']
        with Session.begin() as db:
            stale_original = store.get_transfer(db, identifier)
            user = store.get_user(db, 'trusted')
            assert stale_original.status == 'pending' and stale_original.version == pending['version']
            confirmed = client.post(f'/api/member-claims/{identifier}/confirm', json=dict(
                expected_version=pending['version'], confirmed_amount='1000'))
            assert confirmed.status_code == 200
            assert stale_original.status == 'pending' and stale_original.version == pending['version']
            with pytest.raises(DomainError) as conflict:
                funds.decide(db, user, identifier, pending['version'], rejection=rejection)
            assert conflict.value.status == 409
        current = client.get(f'/api/member-claims/{identifier}').json()
        assert current['status'] == 'posted' and current['outstanding_minor'] == 100000
        assert len(current['transfer']['journal_lines']) == 2
        assert sum(line['debit_minor'] for line in current['transfer']['journal_lines']) == 100000
        overview = client.get(f"/api/members/{decision_member['id']}").json()
        assert overview['ledger_balance_minor'] == overview['outstanding_minor'] == 100000


def repayment_payload(client, m, amount, allocations=None):
    data = dict(member_id=m['id'], source_account_id='fund_pool', amount=amount,
                effective_date='2026-10-13', basis='偿还付款凭据',
                allocation_mode='manual' if allocations is not None else 'oldest_first')
    if allocations is not None: data['allocations'] = allocations
    preview = client.post('/api/repayments/preview', json=data)
    assert preview.status_code == 200
    return dict(data, allocations=preview.json()['allocations'])


def test_repayment_allocation_and_reversal(client):
    m = member(client)
    assert transfer(client, 'opening', 'fund_pool', '2000').status_code == 201
    first = client.post('/api/member-claims', json=claim_payload(m, confirm=True)).json()
    payload = repayment_payload(client, m, '400')
    assert client.get('/api/repayments').json() == []  # Preview has no writes.
    response = client.post('/api/repayments', json=payload)
    assert response.status_code == 201
    payment = response.json()
    assert client.post('/api/repayments', json=payload).status_code == 409
    assert len(client.get('/api/repayments').json()) == 1
    assert client.get('/api/funds/summary').json()['total_minor'] == 160000
    assert client.get(f"/api/member-claims/{first['id']}").json()['outstanding_minor'] == 60000
    assert next(a for a in client.get('/api/accounts').json() if a['id'] == m['account_id'])['balance_minor'] == 60000
    second = client.post('/api/member-claims', json=dict(claim_payload(m, confirm=True), amount='300')).json()
    multi = repayment_payload(client, m, '700')
    assert [(a['claim_id'], a['amount']) for a in multi['allocations']] == [(first['id'], '600.00'), (second['id'], '100.00')]
    response = client.post('/api/repayments', json=multi)
    assert response.status_code == 201
    multi_payment = response.json()
    assert client.get(f"/api/member-claims/{second['id']}").json()['outstanding_minor'] == 20000
    manual = repayment_payload(client, m, '50', [dict(claim_id=second['id'], amount='50')])
    response = client.post('/api/repayments', json=manual)
    assert response.status_code == 201
    manual_payment = response.json()
    other = member(client)
    invalid = dict(manual)
    invalid['allocations'] = [dict(claim_id=second['id'], amount='50')]
    assert client.post('/api/repayments/preview', json=dict(invalid, member_id=other['id'])).status_code == 400
    assert client.post('/api/repayments/preview', json=dict(invalid, amount='60')).status_code == 400
    assert client.post('/api/repayments/preview', json=dict(invalid, amount='151', allocations=[dict(claim_id=second['id'], amount='151')])).status_code == 400
    assert client.post(f"/api/transfers/{second['id']}/reverse", json=dict(reason='撤回')).status_code == 409
    for index, repayment in enumerate([manual_payment, multi_payment, payment]):
        reverse = client.post(f"/api/transfers/{repayment['id']}/reverse", json=dict(reason='撤回付款'))
        assert reverse.status_code == 201 and reverse.json()['amount_minor'] == repayment['amount_minor']
        history = client.get(f"/api/repayments/{repayment['id']}").json()
        assert history['status'] == 'reversed' and not history['effective'] and history['allocations'] == repayment['allocations']
        expected = [(0, 20000), (60000, 30000), (100000, 30000)][index]
        assert tuple(client.get(f"/api/member-claims/{c['id']}").json()['outstanding_minor']
                     for c in [first, second]) == expected
    assert client.get(f"/api/member-claims/{first['id']}").json()['outstanding_minor'] == 100000
    assert client.get(f"/api/member-claims/{second['id']}").json()['outstanding_minor'] == 30000
    for index, claim in enumerate([first, second]):
        assert client.post(f"/api/transfers/{claim['id']}/reverse", json=dict(reason='撤回垫付')).status_code == 201


def test_stale_and_competing_repayments(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.application import member_claims
    from backend.infrastructure import store
    from backend.infrastructure.database import Session
    from backend.kernel.accounting import DomainError

    m = member(client)
    transfer(client, 'opening', 'fund_pool', '2000')
    claim = client.post('/api/member-claims', json=claim_payload(m, confirm=True)).json()
    stale = repayment_payload(client, m, '100')
    current = repayment_payload(client, m, '100')
    assert client.post('/api/repayments', json=current).status_code == 201
    assert client.post('/api/repayments', json=stale).status_code == 409
    remaining = repayment_payload(client, m, '900')
    barrier = Barrier(2)

    def pay(index):
        try:
            with Session.begin() as db:
                # Identity map is deliberately populated before either writer takes the lock.
                original = store.get_transfer(db, claim['id'])
                user = store.get_user(db, 'trusted')
                barrier.wait(timeout=5)
                member_claims.submit_repayment(db, user, remaining)
                assert original.status == 'posted'
            return 201
        except DomainError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(pay, [0, 1]))
    assert sorted(results) == [201, 409]
    payments = client.get('/api/repayments', params={'member_id': m['id']}).json()
    assert len(payments) == 2 and sum(p['amount_minor'] for p in payments) == 100000
    assert client.get(f"/api/member-claims/{claim['id']}").json()['outstanding_minor'] == 0
    assert client.get('/api/funds/summary').json()['total_minor'] == 100000


def test_repayment_write_failure_rolls_back(client):
    import pytest
    from sqlalchemy import text
    from backend.infrastructure.database import engine

    m = member(client)
    transfer(client, 'opening', 'fund_pool', '2000')
    claim = client.post('/api/member-claims', json=claim_payload(m, confirm=True)).json()
    payload = repayment_payload(client, m, '400')
    before = client.get(f"/api/transfers/{claim['id']}").json()
    with engine.begin() as db:
        audit_count = db.scalar(text('SELECT count(*) FROM audit_events'))
        db.execute(text("CREATE OR REPLACE FUNCTION fail_journal() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'induced journal failure'; END $$"))
        db.execute(text('CREATE TRIGGER fail_journal BEFORE INSERT ON journal_lines FOR EACH ROW EXECUTE FUNCTION fail_journal()'))
    try:
        with pytest.raises(Exception, match='induced journal failure'):
            client.post('/api/repayments', json=payload)
        assert client.get('/api/repayments').json() == []
        assert len(client.get('/api/transfers').json()) == 2
        assert client.get('/api/funds/summary').json()['total_minor'] == 200000
        current = client.get(f"/api/member-claims/{claim['id']}").json()
        assert current['outstanding_minor'] == 100000 and current['version'] == before['version']
        assert current['transfer']['audit'] == before['audit']
        with engine.connect() as db:
            assert db.scalar(text('SELECT count(*) FROM repayments')) == 0
            assert db.scalar(text('SELECT count(*) FROM repayment_allocations')) == 0
            assert db.scalar(text('SELECT count(*) FROM audit_events')) == audit_count
            assert db.scalar(text('SELECT count(*) FROM journal_lines')) == 4
    finally:
        with engine.begin() as db:
            db.execute(text('DROP TRIGGER fail_journal ON journal_lines'))
            db.execute(text('DROP FUNCTION fail_journal()'))
