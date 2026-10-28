"""Opt-in, request-scoped webpage agent prototype; business tools remain MCP-owned."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path

import httpx

from backend.application import agent_access
from backend.infrastructure import agent_store
from backend.kernel.accounting import DomainError

MODELS = ('deepseek-flash', 'deepseek-v4-pro')
logger = logging.getLogger(__name__)


def enabled():
    return os.getenv('FGAS_WEB_AGENT_PROTOTYPE') == '1'


def configuration(db, user):
    return {
        'models': list(MODELS),
        'shared_available': bool(os.getenv('FGAS_DEEPSEEK_API_KEY', '').strip()),
        'connections': [
            {'id': item['id'], 'name': item['name'], 'level': item['level'], 'active': item['active']}
            for item in agent_access.list_credentials(db, user)
            if item['owner_user_id'] == user.id and item['level'] == 'low'
            and (item['expires_at'] is None or item['expires_at'] > datetime.now(timezone.utc))
        ],
    }


@dataclass(frozen=True)
class ChatIdentity:
    connection_name: str
    model: str
    source: str
    mcp_secret: str = field(repr=False)
    model_key: str = field(repr=False)


def prepare_chat(db, user, credential_id, model, source, personal_key):
    credential = agent_store.get_by_id(db, credential_id)
    if credential is None or credential.owner_user_id != user.id:
        raise DomainError('请选择你本人的网页助手连接', 403)
    try:
        access = agent_access.resolve(db, credential.secret_value)
    except DomainError as exc:
        if exc.status == 401:
            raise DomainError('所选连接已停用或过期，请在 Agent 连接中核对', 403) from None
        raise
    if access.level != 'low':
        raise DomainError('当前原型使用低权限连接，请选择 low 连接', 403)
    if model not in MODELS:
        raise DomainError('请选择支持的 DeepSeek 模型')
    key = personal_key.strip() if source == 'personal' else os.getenv('FGAS_DEEPSEEK_API_KEY', '').strip()
    if not key:
        raise DomainError('请填写个人 DeepSeek Key' if source == 'personal' else '管理员尚未配置公共 DeepSeek Key')
    return ChatIdentity(credential.name, model, source, credential.secret_value, key)


def _make_model(key, name):
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.deepseek import DeepSeekProvider
    return OpenAIChatModel(name, provider=DeepSeekProvider(api_key=key))


def _event(kind, **values):
    return 'data: ' + json.dumps({'type': kind, **values}, ensure_ascii=False) + '\n\n'


async def chat_events(identity, message, history):
    # No database session is retained while waiting for model or MCP requests.
    from pydantic_ai import Agent, AgentRunResultEvent
    from pydantic_ai.exceptions import ModelAPIError
    from pydantic_ai.messages import (
        FunctionToolCallEvent, FunctionToolResultEvent, ModelRequest, ModelResponse,
        PartStartEvent, PartDeltaEvent, TextPart, TextPartDelta, UserPromptPart,
    )
    from pydantic_ai.mcp import MCPToolset
    from pydantic_ai.usage import UsageLimits

    docs = Path(__file__).resolve().parents[2] / 'docs/ai'
    instructions = '\n\n'.join((docs / name).read_text(encoding='utf-8')
                               for name in ('web-agent.md', 'overview.md'))
    messages = [
        ModelRequest(parts=[UserPromptPart(item['content'])]) if item['role'] == 'user'
        else ModelResponse(parts=[TextPart(item['content'])])
        for item in history
    ]
    # Return business failures to the model and allow limited argument correction.
    # These are agent-loop steps, not automatic replays of completed MCP calls.
    tools = MCPToolset(os.getenv('FGAS_WEB_AGENT_MCP_URL', 'http://127.0.0.1:10632/mcp'),
                       auth=identity.mcp_secret, tool_error_behavior='failed', max_retries=2)
    agent = Agent(_make_model(identity.model_key, identity.model), instructions=instructions,
                  toolsets=[tools], retries=0,
                  model_settings={'max_tokens': 4096, 'parallel_tool_calls': False, 'max_retries': 0})
    yield _event('start', connection=identity.connection_name, source=identity.source, model=identity.model)
    try:
        async with agent.run_stream_events(message, message_history=messages,
                                           usage_limits=UsageLimits(request_limit=10)) as events:
            async for event in events:
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart) and event.part.content:
                    yield _event('text', text=event.part.content)
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    yield _event('text', text=event.delta.content_delta)
                elif isinstance(event, FunctionToolCallEvent):
                    yield _event('tool_start', id=event.part.tool_call_id, name=event.part.tool_name)
                elif isinstance(event, FunctionToolResultEvent):
                    yield _event('tool_end', id=event.part.tool_call_id, name=event.part.tool_name)
                elif isinstance(event, AgentRunResultEvent):
                    usage = event.result.usage
                    yield _event('usage', input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                 cache_read_tokens=usage.cache_read_tokens, requests=usage.requests)
        yield _event('done')
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Provider exceptions may contain request/response details; never echo them to users or logs.
        status = getattr(exc, 'status_code', None)
        message = {401: 'DeepSeek Key 无效，请检查 Key 或主动切换模型来源',
                   402: 'DeepSeek 余额不足，请充值或主动切换模型来源',
                   429: '模型请求暂时受限，请稍后再试'}.get(status,
                   '本轮未能完成，请查看已返回的结果；涉及业务提交时先查询记录再决定下一步')
        logger.warning('Web agent run failed: %s', type(exc).__name__)
        yield _event('error', message=message, configuration_error=isinstance(exc, ModelAPIError))


async def shared_balance(user):
    if user.role != 'admin':
        raise DomainError('仅管理员可查看公共模型余额', 403)
    key = os.getenv('FGAS_DEEPSEEK_API_KEY', '').strip()
    if not key:
        raise DomainError('管理员尚未配置公共 DeepSeek Key')
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get('https://api.deepseek.com/user/balance',
                                        headers={'Authorization': 'Bearer ' + key})
            response.raise_for_status()
            result = response.json()
        return {'available': result['is_available'], 'balances': [
            {'currency': item['currency'], 'total_balance': item['total_balance']}
            for item in result['balance_infos']
        ]}
    except (httpx.HTTPError, KeyError, ValueError):
        raise DomainError('公共模型余额暂时无法查询，请核对 Key 和服务状态', 502) from None
