"""The shared handbook through human HTTP and authenticated MCP paths."""
import asyncio
from datetime import datetime

import httpx2
import pytest
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.entrypoints.http import create_app


def test_handbook_persistence_and_human_permissions(client):
    empty = client.get('/api/handbook')
    assert empty.status_code == 200
    assert empty.json()['content'] == ''
    assert empty.json()['updated_at'] is None
    data = {'title': '社团手册', 'content': '## 发票\n保留纸质票据。\n\n### 报销\n联系财务。'}
    saved = client.put('/api/handbook', json=data)
    assert saved.status_code == 200
    assert saved.json()['updated_by_id'] == 'trusted'
    assert saved.json()['updated_at']
    reloaded = client.get('/api/handbook').json()
    assert {key: reloaded[key] for key in data} == data
    assert reloaded['updated_by_id'] == 'trusted'
    assert reloaded['updated_by_name'] == saved.json()['updated_by_name']
    assert datetime.fromisoformat(reloaded['updated_at']) == datetime.fromisoformat(saved.json()['updated_at'])
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.get('/api/handbook').json()['content'] == data['content']
    assert client.put('/api/handbook', json={**data, 'content': '不允许修改'}).status_code == 403
    assert client.get('/api/handbook').json()['content'] == data['content']
    client.post('/api/auth/login', json={'user_id': 'admin'})
    assert client.put('/api/handbook', json={**data, 'content': ''}).json()['content'] == ''
    client.post('/api/auth/logout')
    assert client.get('/api/handbook').status_code == 401
    assert client.put('/api/handbook', json=data).status_code == 401


@pytest.mark.parametrize('owner,level', [('untrusted', 'low'), ('admin', 'low'), ('trusted', 'high')])
def test_handbook_mcp_access_and_shared_content(client, owner, level):
    original = {'title': '办事说明', 'content': '## 储藏室\n二楼。'}
    assert client.put('/api/handbook', json=original).status_code == 200
    client.post('/api/auth/login', json={'user_id': owner})
    connection = client.post('/api/agent-credentials', json={'name': '手册测试', 'level': level}).json()
    replacement = {'title': '社团手册', 'content': '## 储藏室\n三楼。\n\n### 借用规则\n归还后登记。'}

    async def exercise():
        app = create_app()
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url='http://127.0.0.1:10622',
                                         headers={'Authorization': f"Bearer {connection['secret']}"}) as http:
                async with streamable_http_client('http://127.0.0.1:10622/mcp', http_client=http) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        overview = await session.call_tool('fgas_help', {})
                        assert 'handbook' in overview.structured_content['data']['capabilities']['query']
                        read = await session.call_tool('fgas_query', {'resource': 'handbook'})
                        assert not read.is_error, read.structured_content
                        assert read.structured_content['data']['content'] == original['content']
                        help_result = await session.call_tool('fgas_help', {'topic': 'query', 'resource': 'handbook', 'include_output_schema': True})
                        contract = help_result.structured_content['data']['object']
                        Draft202012Validator(contract['output_schema']).validate(read.structured_content)
                        result = await session.call_tool('fgas_execute', {'resource': 'handbook', 'action': 'update', 'data': replacement})
                        if level == 'low':
                            assert result.is_error and result.structured_content['code'] == 'permission_denied'
                        else:
                            assert not result.is_error, result.structured_content
                            saved = result.structured_content['data']
                            assert saved['object']['content'] == replacement['content']
                            assert saved['object']['updated_by_id'] == owner
                            assert saved['ledger_effect_applied'] is False and saved['approval_required'] is False
                            write_help = await session.call_tool('fgas_help', {'topic': 'execute', 'resource': 'handbook', 'action': 'update', 'include_output_schema': True})
                            Draft202012Validator(write_help.structured_content['data']['output_schema']).validate(result.structured_content)
                            invalid = await session.call_tool('fgas_execute', {'resource': 'handbook', 'action': 'update', 'data': {'title': '不能丢失正文'}})
                            assert invalid.is_error and invalid.structured_content['code'] == 'validation_error'

    asyncio.run(exercise())
    actual = client.get('/api/handbook').json()
    assert actual['content'] == (replacement if level == 'high' else original)['content']
