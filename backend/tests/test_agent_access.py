"""Core Agent behavior through real services, PostgreSQL and the official MCP client."""
from backend.tests.conftest import seed_code
from backend.application.directory_views import by_code
from backend.infrastructure.models import StockAccount
from datetime import date, datetime, timedelta, timezone

import asyncio

import httpx2
import pytest
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import func, select

from backend.application import agent_access, agent_operations as ops, agent_queries as queries
from backend.entrypoints.agent_schemas import AccountPatchOperation
from backend.entrypoints import agent_catalog as catalog
from backend.entrypoints.http import create_app
from backend.infrastructure.database import Session
from backend.infrastructure.models import AgentCredential, JournalLine, StockMove, StockTransfer, Transfer, User
from backend.kernel.accounting import DomainError


def issue(client, level='low', owner='admin', name='测试连接'):
    client.post('/api/auth/login', json={'user_id': owner})
    response = client.post('/api/agent-credentials', json={'name': name, 'level': level})
    assert response.status_code == 200
    return response.json()


def fund_data(source='opening', destination='fund_pool', amount='120.50', date='2026-10-15'):
    source, destination = seed_code(source), seed_code(destination)
    return dict(source_account_code=source, destination_account_code=destination, amount=amount, effective_date=date)


def stock_data(client, code='BOOK-01'):
    source = client.post('/api/stock-accounts', json={'name': '商家', 'kind': 'external'}).json()['code']
    target = client.post('/api/stock-accounts', json={'name': '仓库', 'kind': 'internal'}).json()['code']
    sku = client.post('/api/skus', json={'code': code, 'name': '书', 'unit': '本'}).json()
    return dict(source_account_code=source, destination_account_code=target, effective_date='2026-10-15', lines=[{'sku_code': sku['code'], 'quantity': '2'}])


def test_credential_issue_limits_and_invalidation(client):
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.post('/api/agent-credentials', json={'name': '禁止high', 'level': 'high'}).status_code == 403
    trusted = issue(client, owner='trusted')
    assert client.post('/api/agent-credentials', json={'name': '禁止high', 'level': 'high'}).status_code == 403
    credential, secret = trusted['credential'], trusted['secret']
    listed = client.get('/api/agent-credentials').json()
    assert len(listed) == 1 and listed[0]['id'] == credential['id']
    assert 'secret' not in listed[0] and 'secret_hash' not in listed[0]
    with Session() as db:
        stored = db.get(AgentCredential, credential['id'])
        assert stored.secret_hash == agent_access.hash_secret(secret) and stored.secret_hash != secret
        assert agent_access.resolve(db, secret).user.role == 'trusted'
    with Session.begin() as db:
        db.get(User, 'trusted').role = 'untrusted'
    with Session() as db:
        assert agent_access.resolve(db, secret).user.role == 'untrusted'
    client.post('/api/auth/login', json={'user_id': 'admin'})
    path = f"/api/agent-credentials/{credential['id']}"
    assert client.patch(path, json={'name': '不能改他人'}).status_code == 403
    assert client.patch(path, json={'active': False}).status_code == 200
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, secret)
    assert denied.value.status == 401
    high = issue(client, level='high')
    with Session.begin() as db:
        db.get(AgentCredential, high['credential']['id']).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, high['secret'])
    assert denied.value.status == 401
    with Session.begin() as db:
        db.get(AgentCredential, high['credential']['id']).expires_at = None
        db.get(User, 'admin').role = 'trusted'
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, high['secret'])
    assert denied.value.status == 403
    with Session.begin() as db:
        db.get(User, 'admin').role = 'admin'
        db.get(User, 'admin').active = False
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, high['secret'])
    assert denied.value.status == 403
    # Bearer credentials never establish a human HTTP session.
    client.post('/api/auth/logout')
    assert client.get('/api/agent-credentials', headers={'Authorization': f'Bearer {secret}'}).status_code == 401


@pytest.mark.parametrize('owner,level', [('untrusted', 'low'), ('admin', 'high')])
def test_connection_secret_can_be_viewed_only_by_owner(client, owner, level):
    connection = issue(client, owner=owner, level=level)
    identifier = connection['credential']['id']
    path = f'/api/agent-credentials/{identifier}/secret'
    for _ in range(2):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {'secret': connection['secret']}
        assert response.headers['cache-control'] == 'no-store'
    with Session() as db:
        stored = db.get(AgentCredential, identifier)
        assert stored.secret_value == connection['secret']
        assert agent_access.resolve(db, stored.secret_value).credential_id == identifier
    listed = client.get('/api/agent-credentials').json()
    updated = client.patch(f'/api/agent-credentials/{identifier}', json={'name': '我的 AI'}).json()
    for row in [*listed, updated, connection['credential']]:
        assert not {'secret', 'secret_value', 'secret_hash'} & row.keys()
    for other in ({'trusted', 'admin'} - {owner}):
        client.post('/api/auth/login', json={'user_id': other})
        assert client.get(path).status_code == 403
    client.post('/api/auth/logout')
    assert client.get(path, headers={'Authorization': f"Bearer {connection['secret']}"}).status_code == 401


def test_personal_low_connection_management(client):
    other = issue(client, owner='trusted')
    own = issue(client, owner='untrusted', name='普通用户的 AI')
    path = f"/api/agent-credentials/{own['credential']['id']}"
    listed = client.get('/api/agent-credentials').json()
    assert [row['id'] for row in listed] == [own['credential']['id']]
    assert client.patch(path, json={'name': '我的 AI'}).json()['name'] == '我的 AI'
    assert client.patch(path, json={'level': 'high'}).status_code == 403
    assert client.patch(f"/api/agent-credentials/{other['credential']['id']}", json={'active': False}).status_code == 403
    with Session() as db:
        access = agent_access.resolve(db, own['secret'])
        assert access.user.id == 'untrusted' and access.level == 'low'
        assert queries.list_fund_accounts(db, access, {})['data']['items']
    assert client.patch(path, json={'active': False}).status_code == 200
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, own['secret'])
    assert denied.value.status == 401
    assert client.patch(path, json={'active': True}).status_code == 200
    with Session.begin() as db:
        db.get(User, 'untrusted').active = False
    with Session() as db, pytest.raises(DomainError) as denied:
        agent_access.resolve(db, own['secret'])
    assert denied.value.status == 403


@pytest.mark.parametrize('owner,level', [('untrusted', 'low'), ('trusted', 'low'), ('admin', 'low'), ('admin', 'high')])
def test_proposals_always_require_approval(client, owner, level):
    payload = stock_data(client)
    parent = client.post('/api/stock-transfers', json=payload).json()
    connection = issue(client, level, owner=owner)
    with Session() as db:
        access = agent_access.resolve(db, connection['secret'])
        fund = ops.propose_fund_transfer(db, access, fund_data())['data']
        stock = ops.propose_stock_transfer(db, access, payload)['data']
        completion = ops.propose_stock_completion(db, access, parent['code'], {'effective_date': '2026-10-15'})['data']
        for result in (fund, stock, completion):
            assert result['status'] == 'pending' and result['approval_required'] and not result['ledger_effect_applied']
        db.commit()  # Snapshot reads use their own transaction, as after a real MCP call.
        detail = queries.get_stock_transfer(db, access, parent['code'])['data']
        confirmation = next(c for c in detail['confirmations'] if c['code'] == completion['confirmation_code'])
        assert confirmation['submitted_credential_id'] == connection['credential']['id']
        assert detail['status'] == 'in_transit'
        assert db.scalar(select(func.count()).select_from(JournalLine)) == 0
        assert db.scalar(select(func.count()).select_from(StockMove)) == 0
        assert access.user.id == owner
    if owner == 'untrusted':
        path = f"/api/transfers/{fund['transfer_code']}"
        pending = client.get(path).json()
        assert pending['actor_id'] == owner
        assert pending['submitted_credential_id'] == connection['credential']['id']
        assert client.post(path + '/approve', json={'expected_version': pending['version']}).status_code == 403
        client.post('/api/auth/login', json={'user_id': 'trusted'})
        approved = client.post(path + '/approve', json={'expected_version': pending['version']}).json()
        assert approved['status'] == 'posted' and approved['approved_by'] == 'trusted'
        assert approved['actor_id'] == owner and approved['submitted_credential_id'] == connection['credential']['id']


def test_high_direct_business_and_source(client):
    connection = issue(client, 'high', name='原连接名称')
    low = issue(client)
    with Session() as db:
        access = agent_access.resolve(db, connection['secret'])
        source = ops.create_stock_account(db, access, {'name': 'Agent商家', 'kind': 'external'})['data']['account_code']
        target = ops.create_stock_account(db, access, {'name': 'Agent仓库', 'kind': 'internal'})['data']['account_code']
        created_sku = ops.create_sku(db, access, {'code': 'AGENT-BOOK', 'name': 'Agent书', 'unit': '本'})['data']
        sku = created_sku['sku_code']
        assert created_sku['object']['code'] == 'AGENT-BOOK'
        assert queries.list_skus(db, access, {'q': 'Agent书'})['data']['items'][0]['code'] == sku
        payload = dict(source_account_code=source, destination_account_code=target, effective_date='2026-10-15', lines=[{'sku_code': 'AGENT-BOOK', 'quantity': '2'}])
        member = ops.create_member(db, access, {'name': '测试联系人'})['data']['member_code']
        account = ops.create_fund_account(db, access, {'name': '成员私账', 'kind': 'private', 'member_code': member, 'avatar_url': 'https://example.test/a.png'})['data']['account_code']
        assert queries.list_fund_accounts(db, access, {'q': '成员私账'})['data']['items'][0]['code'] == account
        patch = AccountPatchOperation(identifier=account, name='新名称').model_dump(exclude_unset=True)
        patch.pop('identifier')
        saved = ops.update_fund_account(db, access, account, patch)['data']['object']
        assert saved['member_code'] == member and saved['avatar_url'] == 'https://example.test/a.png'
        saved = ops.update_fund_account(db, access, account, {'member_code': None, 'avatar_url': None})['data']['object']
        assert saved['member_code'] is None and saved['avatar_url'] is None
        expense = ops.create_fund_transfer(db, access, fund_data(account, seed_code('expense'), '2'))['data']
        assert expense['status'] == 'posted' and expense['ledger_effect_applied']
        settlement = ops.create_settlement(db, access, {'transfer': fund_data(seed_code('fund_pool'), account, '2'), 'allocations': [{'item_transfer_code': expense['transfer_code'], 'amount': '2'}]})['data']
        linked = ops.create_stock_operation(db, access, {'stock': payload, 'money': fund_data()})['data']
        stock_id = linked['stock_transfer']['stock_transfer_code']
        assert linked['fund_transfer']['ledger_effect_applied'] and linked['stock_transfer']['status'] == 'in_transit'
        assert db.scalar(select(func.count()).select_from(StockMove)) == 0
        done = ops.complete_stock_transfer(db, access, stock_id, {'effective_date': '2026-10-15'})['data']
        db.commit()
        detail = queries.get_stock_transfer(db, access, stock_id)['data']
        assert done['status'] == 'completed' and done['ledger_effect_applied']
        assert next(c for c in detail['confirmations'] if c['code'] == done['confirmation_code'])['status'] == 'completed'
        assert detail['approval_mode'] == 'agent_direct'
        assert detail['submitted_credential_id'] == access.credential_id
        assert all(a['agent_credential_id'] == access.credential_id for a in detail['audit'])
        assert db.scalar(select(func.count()).select_from(StockMove)) == 1
        reversed_result = ops.reverse_fund_transfer(db, access, expense['transfer_code'], {'reason': '登记更正'})['data']
        for identifier in (settlement['transfer_code'], linked['fund_transfer']['transfer_code'], reversed_result['transfer_code']):
            result = queries.get_fund_transfer(db, access, identifier)['data']
            assert result['submitted_credential_id'] == access.credential_id
            assert result['approval_mode'] == 'agent_direct'
            assert all(a['agent_credential_id'] == access.credential_id for a in result['audit'])
        db.commit()
    client.patch(f"/api/agent-credentials/{connection['credential']['id']}", json={'name': '后来改名'})
    with Session() as db:
        access = agent_access.resolve(db, connection['secret'])
        assert queries.get_stock_transfer(db, access, stock_id)['data']['submitted_credential_name'] == '原连接名称'
        with pytest.raises(DomainError) as denied:
            ops.create_member(db, agent_access.resolve(db, low['secret']), {'name': '禁止'})
        assert denied.value.status == 403


def test_queries_support_disambiguation_and_submission_lookup(client):
    low, high = issue(client), issue(client, 'high')
    member = client.post('/api/members', json={'name': '联系人', 'note': '负责教材采购'}).json()['code']
    for kind in ('public', 'private'):
        client.post('/api/accounts', json={'name': '同名', 'kind': kind, 'member_code': member})
    payload = stock_data(client)
    custody = client.patch(f"/api/stock-accounts/{payload['destination_account_code']}", json={'member_code': member})
    assert custody.status_code == 200
    parent = client.post('/api/stock-transfers', json=payload).json()
    start = datetime(2026, 10, 15, tzinfo=timezone.utc)
    with Session() as db:
        access = agent_access.resolve(db, low['secret'])
        high_access = agent_access.resolve(db, high['secret'])
        selected, values = catalog.prepare_call('fgas_query', {'resource': 'members', 'filters': {'q': '联系人'}})
        contacts = selected.output_model.model_validate(selected.handler(db, access, values)).data.items
        assert [(row.code, row.note) for row in contacts] == [(member, '负责教材采购')]
        selected, values = catalog.prepare_call('fgas_query', {'resource': 'stock_accounts', 'filters': {'q': '仓库'}})
        accounts = selected.output_model.model_validate(selected.handler(db, access, values)).data.items
        assert accounts[0].member_code == member
        assert accounts[0].member_name == '联系人'
        candidates = queries.list_fund_accounts(db, access, {'q': '同名'})['data']['items']
        assert {row['kind'] for row in candidates} == {'public', 'private'}
        assert all(row['member_name'] == '联系人' and row['active'] for row in candidates)
        assert queries.list_fund_accounts(db, high_access, {'q': '同名'})['data']['items'] == candidates
        identifiers = []
        for index, date in enumerate(('2026-10-14', '2026-10-15', '2026-10-16')):
            identifier = ops.propose_fund_transfer(db, access, fund_data(date=date))['data']['transfer_code']
            by_code(db, Transfer, identifier).created_at = start + timedelta(hours=index)
            identifiers.append(identifier)
        ops.propose_fund_transfer(db, high_access, fund_data())
        filters = {'submitted_by_current_connection': True, 'limit': 2}
        first = queries.list_fund_transfers(db, access, filters)['data']
        second = queries.list_fund_transfers(db, access, filters | {'page': 2})['data']
        assert first['has_more'] and not second['has_more']
        assert [row['code'] for row in first['items'] + second['items']] == list(reversed(identifiers))
        dated = queries.list_fund_transfers(db, access, filters | {'effective_date_from': '2026-10-14', 'effective_date_to': '2026-10-15'})['data']
        assert {row['code'] for row in dated['items']} == set(identifiers[:2])
        timed = queries.list_fund_transfers(db, access, filters | {'created_at_from': start.isoformat(), 'created_at_to': (start + timedelta(hours=1)).isoformat()})['data']
        assert [row['code'] for row in timed['items']] == identifiers[:1]
        first_completion = ops.propose_stock_completion(db, access, parent['code'], {'effective_date': '2026-10-15'})['data']['confirmation_code']
        ops.reject_stock_completion(db, high_access, first_completion, {'reason': '重新核对'})
        second_completion = ops.propose_stock_completion(db, access, parent['code'], {'effective_date': '2026-10-15'})['data']['confirmation_code']
        completions = [first_completion, second_completion]
        found = queries.list_stock_transfers(db, access, {'submitted_by_current_connection': True, 'limit': 1})['data']
        assert [row['code'] for row in found['items']] == [parent['code']] and not found['has_more']
        db.commit()  # Snapshot reads use their own transaction, as after a real MCP call.
        detail = queries.get_stock_transfer(db, access, parent['code'])['data']
        assert {c['code'] for c in detail['confirmations']} == set(completions)
        assert queries.minor_to_yuan(-1) == '-0.01' and queries.minor_to_yuan(12050) == '120.50'
        assert first['items'][0]['amount_minor'] == 12050 and first['items'][0]['amount'] == '120.50'


def test_independent_apps_start_on_separate_event_loops(client):
    connection = issue(client)

    async def query_accounts():
        app = create_app()
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url='http://127.0.0.1:10622',
                headers={'Authorization': f"Bearer {connection['secret']}"},
            ) as http:
                async with streamable_http_client('http://127.0.0.1:10622/mcp', http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        assert 'fgas_query' in {tool.name for tool in (await session.list_tools()).tools}
                        result = await session.call_tool('fgas_query', {'resource': 'fund_accounts'})
                        assert not result.is_error
                        return result.structured_content['data']['items']

    first = asyncio.run(query_accounts())
    second = asyncio.run(query_accounts())
    assert first and second == first


@pytest.mark.parametrize('owner,level', [('untrusted', 'low'), ('admin', 'low'), ('admin', 'high')])
def test_mcp_auth_discovery_and_structured_results(client, owner, level):
    stock = stock_data(client)
    responsible = client.post('/api/members', json={'name': '仓库负责人'}).json()['code']
    assert client.patch('/api/stock-accounts/' + stock['destination_account_code'], json={'member_code': responsible}).status_code == 200
    sku_ids = {client.get('/api/skus', params={'code': stock['lines'][0]['sku_code']}).json()[0]['code']}
    for index in range(20):
        response = client.post('/api/skus', json={'code': f'PAGE-{index:02}', 'name': f'分页货物{index:02}', 'unit': '件'})
        assert response.status_code == 201
        sku_ids.add(response.json()['code'])
    private_id = client.post('/api/accounts', json={'name': '待匹配私账', 'kind': 'private'}).json()['code']
    expense = client.post('/api/transfers', json=fund_data(private_id, seed_code('expense'), '2')).json()
    payment = client.post('/api/transfers', json=fund_data(seed_code('fund_pool'), private_id, '2')).json()
    connection = issue(client, owner=owner, level=level, name='身份验证连接')
    with Session() as db:
        user = db.get(User, owner)
        expected_identity = {'user': {'display_name': user.display_name, 'role': user.role},
                             'connection': {'name': '身份验证连接', 'level': level}}
    for headers in ({}, {'Authorization': 'Bearer invalid'}, {'Cookie': '; '.join(f'{k}={v}' for k, v in client.cookies.items())}):
        assert client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}}, headers=headers).status_code == 401

    async def exercise():
        app = create_app()
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='http://127.0.0.1:10622', headers={'Authorization': f"Bearer {connection['secret']}"}) as http:
                async with streamable_http_client('http://127.0.0.1:10622/mcp', http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        tools = (await session.list_tools()).tools
                        names = {tool.name for tool in tools}
                        assert names == {'fgas_help', 'fgas_query', 'fgas_propose'} | ({'fgas_execute'} if level == 'high' else set())
                        assert all(tool.input_schema and tool.output_schema for tool in tools)
                        overview = await session.call_tool('fgas_help', {})
                        assert overview.structured_content['data']['level'] == level
                        identity = await session.call_tool('fgas_query', {'resource': 'me'})
                        assert not identity.is_error
                        assert identity.structured_content == {'api_version': '2', 'data': expected_identity}
                        identity_help = await session.call_tool('fgas_help', {'topic': 'query', 'resource': 'me', 'include_output_schema': True})
                        contract = identity_help.structured_content['data']['object']
                        Draft202012Validator(contract['output_schema']).validate(identity.structured_content)
                        _, prepared = catalog.prepare_call('fgas_query', contract['example'])
                        assert prepared == {}
                        for unsupported in ({'identifier': 'admin'}, {'filters': {'user_id': 'admin'}},
                                            {'filters': {'page': 1}}, {'filters': {'as_of': '2026-10-01T00:00:00+08:00'}}):
                            rejected = await session.call_tool('fgas_query', {'resource': 'me', **unsupported})
                            assert rejected.is_error and rejected.structured_content['code'] == 'validation_error'
                        if level == 'high':
                            return
                        read = await session.call_tool('fgas_query', {'resource': 'fund_accounts'})
                        assert not read.is_error and read.structured_content['api_version'] == '2'
                        assert read.structured_content['data']['items']
                        stock_account = await session.call_tool('fgas_query', {'resource': 'stock_accounts', 'identifier': stock['destination_account_code']})
                        assert not stock_account.is_error
                        assert stock_account.structured_content['data']['member_code'] == responsible
                        assert stock_account.structured_content['data']['responsibility_history'][0]['member_code'] == responsible
                        windowed = await session.call_tool('fgas_query', {'resource': 'fund_transfers', 'filters': {'all_time': True}})
                        assert not windowed.is_error
                        unmatched = []
                        for page in (1, 2):
                            result = await session.call_tool('fgas_query', {'resource': 'settlement_outstanding', 'filters': {'page': page, 'limit': 1}})
                            assert not result.is_error, result.structured_content
                            data = result.structured_content['data']
                            assert data['total'] == 2 and data['has_more'] == (page == 1)
                            assert data['items'][0]['remaining'] == '2.00'
                            unmatched.extend(row['transfer_code'] for row in data['items'])
                        assert unmatched == [payment['code'], expense['code']]
                        contract = await session.call_tool('fgas_help', {
                            'topic': 'query', 'resource': 'settlement_outstanding', 'include_output_schema': True,
                        })
                        assert not contract.is_error
                        Draft202012Validator(contract.structured_content['data']['list']['output_schema']).validate(result.structured_content)
                        denied_match = await session.call_tool('fgas_execute', {
                            'resource': 'settlement', 'action': 'match', 'data': {
                                'identifier': payment['code'], 'allocations': [{'item_transfer_code': expense['code'], 'amount': '2'}],
                            },
                        })
                        assert denied_match.is_error and denied_match.structured_content['code'] == 'permission_denied'
                        as_of = await session.call_tool('fgas_query', {'resource': 'inventory', 'filters': {'as_of': '2026-10-01T00:00:00+08:00'}})
                        assert not as_of.is_error and as_of.structured_content['data']['basis'] == 'posted'
                        assert all(row['in_transit_planned_quantity'] is None for row in as_of.structured_content['data']['items'])
                        pages = []
                        for page, limit in ((1, 20), (2, 20), (1, 100)):
                            result = await session.call_tool('fgas_query', {'resource': 'inventory', 'filters': {
                                'account_code': stock['destination_account_code'], 'page': page, 'limit': limit,
                            }})
                            assert not result.is_error
                            pages.append(result.structured_content['data'])
                        first, second, large = pages
                        assert len(first['items']) == 20 and first['has_more']
                        assert len(second['items']) == 1 and not second['has_more']
                        assert {row['sku_code'] for row in first['items'] + second['items']} == sku_ids
                        assert len(large['items']) == 21 and not large['has_more']
                        assert {row['sku_code'] for row in large['items']} == sku_ids
                        assert first['totals'] == second['totals'] == large['totals']
                        help_result = await session.call_tool('fgas_help', {'topic': 'query', 'resource': 'inventory'})
                        assert not help_result.is_error
                        assert 'output_schema' not in help_result.structured_content['data']['list']
                        full_help = await session.call_tool('fgas_help', {
                            'topic': 'query', 'resource': 'inventory', 'include_output_schema': True,
                        })
                        assert not full_help.is_error
                        Draft202012Validator(full_help.structured_content['data']['list']['output_schema']).validate(
                            {'api_version': '2', 'data': large})
                        inventory = await session.call_tool('fgas_query', {'resource': 'inventory', 'filters': {
                            'account_code': stock['destination_account_code'], 'sku_code': 'BOOK-01',
                        }})
                        assert not inventory.is_error
                        assert [(row['sku_code'], row['quantity']) for row in inventory.structured_content['data']['items']] == [('BOOK-01', '0')]
                        stock_proposal = await session.call_tool('fgas_propose', {'resource': 'stock_transfer', 'data': stock})
                        assert not stock_proposal.is_error, stock_proposal.structured_content
                        stock_result = stock_proposal.structured_content['data']
                        assert stock_result['status'] == 'pending' and stock_result['approval_required'] and not stock_result['ledger_effect_applied']
                        stock_query = await session.call_tool('fgas_query', {'resource': 'stock_transfers', 'filters': {'sku_code': 'BOOK-01'}})
                        assert not stock_query.is_error
                        assert [(row['code'], row['lines'][0]['sku_code']) for row in stock_query.structured_content['data']['items']] == [(stock_result['stock_transfer_code'], 'BOOK-01')]
                        other_stock = await session.call_tool('fgas_query', {'resource': 'stock_transfers', 'filters': {'sku_code': 'PAGE-00'}})
                        assert not other_stock.is_error and other_stock.structured_content['data']['items'] == []
                        proposed = await session.call_tool('fgas_propose', {'resource': 'fund_transfer', 'data': fund_data()})
                        assert not proposed.is_error and proposed.structured_content['data']['status'] == 'pending'
                        detail = await session.call_tool('fgas_query', {'resource': 'fund_transfers', 'identifier': proposed.structured_content['data']['transfer_code']})
                        assert detail.structured_content['data']['status'] == 'pending'
                        denied = await session.call_tool('fgas_execute', {'resource': 'member', 'action': 'create', 'data': {'name': '不能猜高权限工具'}})
                        assert denied.is_error and denied.structured_content['code'] == 'permission_denied'
                        denied_sku = await session.call_tool('fgas_execute', {'resource': 'sku', 'action': 'create', 'data': {'code': 'DENIED-01', 'name': '禁止创建', 'unit': '本'}})
                        assert denied_sku.is_error and denied_sku.structured_content['code'] == 'permission_denied'
                        old = await session.call_tool('fgas_propose_fund_transfer', fund_data())
                        assert old.is_error and old.structured_content['code'] == 'tool_migrated'
                        invalid = await session.call_tool('fgas_propose', {'resource': 'fund_transfer', 'data': {}})
                        assert invalid.is_error
                        assert 'data.amount' in {field['field'] for field in invalid.structured_content['fields']}
                        assert invalid.structured_content['help']['arguments']['resource'] == 'fund_transfer'
                        # Disabling the credential affects a new call in the same SDK session.
                        with Session.begin() as db:
                            db.get(AgentCredential, connection['credential']['id']).active = False
                        response = await http.post('http://127.0.0.1:10622/mcp', json={'jsonrpc': '2.0', 'id': 99, 'method': 'tools/list'})
                        assert response.status_code == 401
    asyncio.run(exercise())



def test_compact_help_contract_and_patch_inputs():
    help_data = catalog.help_data('high', topic='execute', resource='fund_account', action='update')
    assert 'output_schema' not in help_data
    _, values = catalog.prepare_call('fgas_execute', help_data['example'])
    assert values == {'identifier': 'FA-0001', 'name': '新的账户名称'}
    _, cleared = catalog.prepare_call('fgas_execute', {
        'resource': 'fund_account', 'action': 'update',
        'data': {'identifier': 'FA-0001', 'avatar_url': None},
    })
    assert cleared == {'identifier': 'FA-0001', 'avatar_url': None}
    _, created = catalog.prepare_call('fgas_execute', {
        'resource': 'member', 'action': 'create', 'data': {'name': '联系人'},
    })
    assert created == {'name': '联系人', 'note': ''}
    index = catalog.help_data('low', topic='query')
    assert all('input_schema' not in entry for entry in index['resources'])
    with pytest.raises(DomainError) as denied:
        catalog.help_data('low', topic='execute', resource='member', action='create')
    assert denied.value.status == 403


@pytest.mark.parametrize('arguments, field', [
    ({'resource': 'fund_transfers', 'identifier': 'id', 'filters': {'status': 'pending'}}, 'filters'),
    ({'resource': 'members', 'identifier': 'id'}, 'identifier'),
    ({'resource': 'me', 'identifier': 'admin'}, 'identifier'),
    *[({'resource': 'me', 'filters': {key: value}}, 'filters.' + key) for key, value in (
        ('user_id', 'admin'), ('role', 'admin'), ('level', 'high'), ('name', 'other'),
        ('page', 1), ('limit', 20), ('as_of', '2026-10-01T00:00:00+08:00'))],
    ({'resource': 'fund_transfers', 'filters': {'amount': '100'}}, 'filters.amount'),
    ({'resource': 'fund_transfers', 'filters': {'status': 'approved'}}, 'filters.status'),
    ({'resource': 'stock_transfers', 'filters': {'status': 'posted'}}, 'filters.status'),
])
def test_compact_query_rejects_ignored_parameters(arguments, field):
    with pytest.raises(catalog.InputProblem) as error:
        catalog.prepare_call('fgas_query', arguments)
    assert field in {item['field'] for item in error.value.fields}


def test_mcp_high_execution_uses_real_business_services(client):
    connection = issue(client, 'high')
    payload = stock_data(client)

    async def exercise():
        app = create_app()
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='http://127.0.0.1:10622', headers={'Authorization': f"Bearer {connection['secret']}"}) as http:
                async with streamable_http_client('http://127.0.0.1:10622/mcp', http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        assert (await session.initialize()).instructions
                        assert {tool.name for tool in (await session.list_tools()).tools} == {'fgas_help', 'fgas_query', 'fgas_propose', 'fgas_execute'}

                        async def execute(resource, action, data):
                            result = await session.call_tool('fgas_execute', dict(resource=resource, action=action, data=data))
                            assert not result.is_error, result.structured_content
                            return result.structured_content['data']

                        sku = await execute('sku', 'create', {'code': 'MCP-BOOK', 'name': 'MCP刊物', 'unit': '本', 'tags': ['角色:博丽灵梦']})
                        assert sku['object']['code'] == 'MCP-BOOK'
                        by_code = await session.call_tool('fgas_query', {'resource': 'skus', 'filters': {'code': 'MCP-BOOK'}})
                        assert not by_code.is_error
                        assert [row['code'] for row in by_code.structured_content['data']['items']] == [sku['sku_code']]
                        by_role = await session.call_tool('fgas_query', {'resource': 'skus', 'filters': {'tag': '角色:博丽灵梦'}})
                        assert not by_role.is_error
                        assert [row['code'] for row in by_role.structured_content['data']['items']] == ['MCP-BOOK']
                        payload['lines'] = [{'sku_code': 'MCP-BOOK', 'quantity': '2'}]
                        responsible = await execute('member', 'create', {'name': 'MCP负责人'})
                        assigned = await execute('stock_account', 'update', {'identifier': payload['destination_account_code'], 'member_code': responsible['member_code']})
                        assert assigned['object']['member_code'] == responsible['member_code']
                        history = await session.call_tool('fgas_query', {'resource': 'stock_accounts', 'identifier': payload['destination_account_code']})
                        assert not history.is_error and len(history.structured_content['data']['responsibility_history']) == 1
                        account = await execute('fund_account', 'create', {'name': 'MCP私账', 'kind': 'private', 'avatar_url': 'https://example.test/avatar.png'})
                        account_code = account['account_code']
                        renamed = await execute('fund_account', 'update', {'identifier': account_code, 'name': '改名私账'})
                        assert renamed['object']['avatar_url'] == 'https://example.test/avatar.png'
                        cleared = await execute('fund_account', 'update', {'identifier': account_code, 'avatar_url': None})
                        assert cleared['object']['avatar_url'] is None
                        expense = await execute('fund_transfer', 'create', fund_data(account_code, seed_code('expense'), '2'))
                        assert expense['status'] == 'posted' and expense['ledger_effect_applied']
                        payment = await execute('fund_transfer', 'create', fund_data(seed_code('fund_pool'), account_code, '2'))
                        matched = await execute('settlement', 'match', {'identifier': payment['transfer_code'], 'allocations': [{'item_transfer_code': expense['transfer_code'], 'amount': '2'}]})
                        assert not matched['ledger_effect_applied'] and matched['matches'][0]['amount'] == '2.00'
                        remaining = await session.call_tool('fgas_query', {'resource': 'settlement_outstanding'})
                        assert not remaining.is_error and remaining.structured_content['data']['items'] == []
                        proposal = await session.call_tool('fgas_propose', {'resource': 'fund_transfer', 'data': fund_data()})
                        assert proposal.structured_content['data']['status'] == 'pending'
                        stock = await execute('stock_transfer', 'create', payload)
                        assert stock['status'] == 'in_transit' and not stock['ledger_effect_applied']
                        completion = await execute('stock_transfer', 'complete', {'identifier': stock['stock_transfer_code'], 'effective_date': '2026-10-15'})
                        assert completion['status'] == 'completed' and completion['ledger_effect_applied']
                        detail = await session.call_tool('fgas_query', {'resource': 'stock_transfers', 'identifier': stock['stock_transfer_code']})
                        assert detail.structured_content['data']['submitted_credential_id'] == connection['credential']['id']
                        invalid = await session.call_tool('fgas_execute', {'resource': 'member', 'action': 'approve', 'data': {}})
                        assert invalid.is_error
        with Session() as db:
            assert db.scalar(select(func.count()).select_from(JournalLine)) == 4
            assert db.scalar(select(func.count()).select_from(StockMove)) == 1
    asyncio.run(exercise())



def test_help_describes_non_null_patch_and_combined_result():
    help_data = catalog.help_data('high', topic='execute', resource='fund_account', action='update')
    example = help_data['example']
    invalid = example | {'data': {'identifier': 'FA-0001', 'name': None}}
    assert not Draft202012Validator(help_data['input_schema']).is_valid(invalid)
    with pytest.raises(catalog.InputProblem) as error:
        catalog.prepare_call('fgas_execute', invalid)
    assert error.value.fields[0]['field'] == 'data.name'
    cleared = example | {'data': {'identifier': 'FA-0001', 'avatar_url': None}}
    Draft202012Validator(help_data['input_schema']).validate(cleared)
    combined = catalog.help_data('high', topic='execute', resource='stock_operation', action='create', include_output_schema=True)
    Draft202012Validator(combined['output_schema']).validate({'api_version': '2', 'data': {
        'resource_type': 'stock_operation',
        'fund_transfer': {'resource_type': 'fund_transfer', 'transfer_code': 'fund-id', 'status': 'posted', 'ledger_effect_applied': True, 'approval_required': False},
        'stock_transfer': {'resource_type': 'stock_transfer', 'stock_transfer_code': 'stock-id', 'status': 'in_transit', 'ledger_effect_applied': False, 'approval_required': False},
    }})


def test_event_lists_default_window_and_all_time(client):
    low = issue(client)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    old_stock_payload = stock_data(client)
    recent_stock_payload = stock_data(client, 'BOOK-02')
    with Session() as db:
        access = agent_access.resolve(db, low['secret'])
        old_fund = ops.propose_fund_transfer(db, access, fund_data())['data']['transfer_code']
        recent_fund = ops.propose_fund_transfer(db, access, fund_data())['data']['transfer_code']
        by_code(db, Transfer, old_fund).created_at = old
        old_stock = ops.propose_stock_transfer(db, access, old_stock_payload)['data']['stock_transfer_code']
        recent_stock = ops.propose_stock_transfer(db, access, recent_stock_payload)['data']['stock_transfer_code']
        by_code(db, StockTransfer, old_stock).created_at = old
        db.commit()
        default_fund = {row['code'] for row in queries.list_fund_transfers(db, access, {})['data']['items']}
        assert recent_fund in default_fund and old_fund not in default_fund
        all_fund = {row['code'] for row in queries.list_fund_transfers(db, access, {'all_time': True})['data']['items']}
        assert {old_fund, recent_fund} <= all_fund
        explicit_fund = {row['code'] for row in queries.list_fund_transfers(db, access, {'created_at_from': (old - timedelta(days=1)).isoformat()})['data']['items']}
        assert {old_fund, recent_fund} <= explicit_fund
        default_stock = {row['code'] for row in queries.list_stock_transfers(db, access, {})['data']['items']}
        assert recent_stock in default_stock and old_stock not in default_stock
        all_stock = {row['code'] for row in queries.list_stock_transfers(db, access, {'all_time': True})['data']['items']}
        assert {old_stock, recent_stock} <= all_stock


def test_event_window_bypass_and_detail_exemption(client):
    low = issue(client)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    with Session() as db:
        access = agent_access.resolve(db, low['secret'])
        identifier = ops.propose_fund_transfer(db, access, fund_data(date='2026-09-01'))['data']['transfer_code']
        by_code(db, Transfer, identifier).created_at = old
        db.commit()
        assert identifier not in {row['code'] for row in queries.list_fund_transfers(db, access, {})['data']['items']}
        bypassed = queries.list_fund_transfers(db, access, {'effective_date_from': '2026-09-01', 'effective_date_to': '2026-09-01'})['data']['items']
        assert [row['code'] for row in bypassed] == [identifier]
        assert queries.get_fund_transfer(db, access, identifier)['data']['code'] == identifier


def test_fund_balance_as_of_and_reversal(client):
    high = issue(client, 'high')
    as_of = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    with Session() as db:
        access = agent_access.resolve(db, high['secret'])
        posted = ops.create_fund_transfer(db, access, fund_data(seed_code('opening'), seed_code('fund_pool'), '120.50', '2026-10-15'))['data']['transfer_code']
        assert by_code(db, Transfer, posted).posted_at is not None
        by_code(db, Transfer, posted).posted_at = as_of
        pending = ops.propose_fund_transfer(db, access, fund_data(seed_code('opening'), seed_code('fund_pool'), '5', '2026-10-15'))['data']['transfer_code']
        db.commit()

        def balance(when, basis='posted'):
            data = queries.get_fund_balances(db, access, {'as_of': when.isoformat(), 'basis': basis})['data']
            row = next(item for item in data['items'] if item['code'] == seed_code('fund_pool'))
            return row['balance_minor'], data['total_minor']

        assert balance(as_of - timedelta(seconds=1)) == (0, 0)
        assert balance(as_of + timedelta(seconds=1)) == (12050, 12050)
        assert by_code(db, Transfer, pending).posted_at is None

        reversal = ops.reverse_fund_transfer(db, access, posted, {'reason': '更正'})['data']['transfer_code']
        by_code(db, Transfer, reversal).posted_at = as_of + timedelta(hours=1)
        db.commit()
        assert by_code(db, Transfer, posted).status == 'reversed'
        assert db.scalar(select(func.count()).select_from(JournalLine).where(JournalLine.transfer_id == by_code(db,Transfer,posted).id)) == 2
        assert balance(as_of + timedelta(minutes=30)) == (12050, 12050)
        assert balance(as_of + timedelta(hours=2)) == (0, 0)

        backdated = ops.create_fund_transfer(db, access, fund_data(seed_code('opening'), seed_code('fund_pool'), '50', '2026-09-01'))['data']['transfer_code']
        by_code(db, Transfer, backdated).posted_at = as_of + timedelta(hours=3)
        db.commit()
        assert balance(as_of + timedelta(minutes=30), 'posted') == (12050, 12050)
        assert balance(as_of + timedelta(minutes=30), 'effective_date') == (5000, 5000)


def test_inventory_as_of_onhand_and_null_in_transit(client):
    high = issue(client, 'high')
    payload = stock_data(client)
    sku = client.get('/api/skus', params={'code': payload['lines'][0]['sku_code']}).json()[0]
    target = payload['destination_account_code']
    as_of = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    with Session() as db:
        access = agent_access.resolve(db, high['secret'])
        stock = ops.create_stock_transfer(db, access, payload)['data']['stock_transfer_code']
        db.commit()
        current = queries.get_inventory(db, access, {'account_code': target})['data']['items'][0]
        assert current['quantity'] == '0' and current['in_transit_planned_quantity'] == '2'
        historical = queries.get_inventory(db, access, {'account_code': target, 'as_of': as_of.isoformat()})['data']['items'][0]
        assert historical['quantity'] == '0' and historical['in_transit_planned_quantity'] is None

        ops.complete_stock_transfer(db, access, stock, {'effective_date': '2026-10-15'})
        move = db.scalar(select(StockMove).order_by(StockMove.created_at.desc()))
        move.created_at = as_of
        db.commit()
        before = queries.get_inventory(db, access, {'account_code': target, 'as_of': (as_of - timedelta(seconds=1)).isoformat()})['data']
        assert before['items'][0]['quantity'] == '0' and before['items'][0]['in_transit_planned_quantity'] is None
        after = queries.get_inventory(db, access, {'account_code': target, 'as_of': (as_of + timedelta(seconds=1)).isoformat()})['data']
        assert after['items'][0]['quantity'] == '2' and after['items'][0]['in_transit_planned_quantity'] is None
        assert after['totals'] == [{'sku_code': sku['code'], 'quantity': '2', 'valuation': '未估值'}]
        current_after = queries.get_inventory(db, access, {'account_code': target})['data']['items'][0]
        assert current_after['quantity'] == '2' and current_after['in_transit_planned_quantity'] == '0'


def test_stock_move_filters_sql(client):
    high = issue(client, 'high')
    first_payload = stock_data(client)
    second_payload = stock_data(client, 'BOOK-02')
    old = datetime.now(timezone.utc) - timedelta(days=40)
    with Session() as db:
        access = agent_access.resolve(db, high['secret'])
        first = ops.create_stock_transfer(db, access, first_payload)['data']['stock_transfer_code']
        ops.complete_stock_transfer(db, access, first, {'effective_date': '2026-10-01'})
        second = ops.create_stock_transfer(db, access, second_payload)['data']['stock_transfer_code']
        ops.complete_stock_transfer(db, access, second, {'effective_date': '2026-10-15'})
        moves = list(db.scalars(select(StockMove)))
        old_move = next(move for move in moves if move.effective_date == date(2026, 10, 1))
        old_move.created_at = old
        db.commit()
        default = {row['stock_transfer_code'] for row in queries.list_stock_moves(db, access, {})['data']['items']}
        assert default == {second}
        all_rows = {row['stock_transfer_code'] for row in queries.list_stock_moves(db, access, {'all_time': True})['data']['items']}
        assert all_rows == {first,second}
        first_page = queries.list_stock_moves(db, access, {'all_time': True, 'limit': 1})['data']
        second_page = queries.list_stock_moves(db, access, {'all_time': True, 'limit': 1, 'page': 2})['data']
        assert first_page['has_more'] and not second_page['has_more']
        assert first_page['items'][0]['stock_transfer_code'] == second
        assert second_page['items'][0]['stock_transfer_code'] == first
        by_effective = queries.list_stock_moves(db, access, {'effective_date_from': '2026-10-01', 'effective_date_to': '2026-10-01'})['data']['items']
        assert [row['stock_transfer_code'] for row in by_effective] == [first]
        by_created = queries.list_stock_moves(db, access, {
            'created_at_from': (old - timedelta(days=1)).isoformat(),
            'created_at_to': (old + timedelta(days=1)).isoformat(),
        })['data']['items']
        assert [row['stock_transfer_code'] for row in by_created] == [first]
        by_posted = queries.list_stock_moves(db, access, {
            'posted_at_from': (old - timedelta(days=1)).isoformat(),
            'posted_at_to': (old + timedelta(days=1)).isoformat(),
        })['data']['items']
        assert [row['stock_transfer_code'] for row in by_posted] == [first]


def test_help_schemas_for_windows_and_as_of():
    for resource, valid, invalid_status in [('fund_transfers', 'posted', 'approved'), ('stock_transfers', 'in_transit', 'posted')]:
        schema = catalog.help_data('low', topic='query', resource=resource)['list']['input_schema']
        validator = Draft202012Validator(schema)
        validator.validate({'resource': resource, 'filters': {'status': valid}})
        assert not validator.is_valid({'resource': resource, 'filters': {'status': invalid_status}})
    help_validator = Draft202012Validator(catalog.HelpInput.model_json_schema())
    help_validator.validate({'topic': 'execute', 'resource': 'fund_transfer', 'action': 'approve'})
    assert not help_validator.is_valid({'topic': 'execute', 'resource': 'fund_transfer', 'action': 'aprove'})
    assert not help_validator.is_valid({'topic': 'query', 'resource': 'fund_transferz'})
    _, values = catalog.prepare_call('fgas_query', {'resource': 'fund_transfers', 'filters': {'all_time': True}})
    assert values['all_time'] is True
    _, values = catalog.prepare_call('fgas_query', {
        'resource': 'fund_balances',
        'filters': {'as_of': '2026-10-01T00:00:00+08:00', 'basis': 'effective_date'},
    })
    assert values['basis'] == 'effective_date'
    with pytest.raises(catalog.InputProblem) as invalid:
        catalog.prepare_call('fgas_query', {
            'resource': 'stock_transfers',
            'filters': {'posted_at_from': '2026-10-01T00:00:00+08:00'},
        })
    assert 'filters.posted_at_from' in {item['field'] for item in invalid.value.fields}
    with pytest.raises(catalog.InputProblem):
        catalog.prepare_call('fgas_query', {'resource': 'fund_balances', 'filters': {'as_of': '2026-10-01T00:00:00'}})
    with pytest.raises(catalog.InputProblem):
        catalog.prepare_call('fgas_query', {
            'resource': 'fund_balances',
            'filters': {'as_of': '2026-10-01T00:00:00+08:00', 'basis': 'created_at'},
        })
    schema = catalog.help_data('low', topic='query', resource='fund_balances')['list']['input_schema']
    assert 'as_of' in str(schema) and 'basis' in str(schema)
    move_schema = catalog.help_data('low', topic='query', resource='stock_moves')['list']['input_schema']
    assert 'posted_at_from' in str(move_schema) and 'all_time' in str(move_schema)
