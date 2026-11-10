"""Opt-in, request-scoped webpage agent prototype; business tools remain MCP-owned."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path

import httpx

from backend.application import agent_access
from backend.application.identity import authorize_write, require_admin
from backend.infrastructure import agent_store, web_agent_store
from backend.kernel.accounting import DomainError

MODELS = ('deepseek-flash', 'deepseek-v4-pro')
logger = logging.getLogger(__name__)


def enabled():
    return os.getenv('FGAS_WEB_AGENT_PROTOTYPE') == '1'


def _shared_key(db):
    return web_agent_store.get_key(db) or os.getenv('FGAS_DEEPSEEK_API_KEY', '').strip()


def shared_configuration(db, user):
    require_admin(user)
    saved = bool(web_agent_store.get_key(db))
    source = 'database' if saved else 'environment' if os.getenv('FGAS_DEEPSEEK_API_KEY', '').strip() else None
    return dict(configured=source is not None, source=source, database_configured=saved)


def save_shared_key(db, user, key):
    authorize_write(db, user, trusted=False)
    require_admin(user)
    key = key.strip()
    if not key:
        raise DomainError('公共 DeepSeek Key 不能为空')
    web_agent_store.save_key(db, key)
    return shared_configuration(db, user)


def clear_shared_key(db, user):
    authorize_write(db, user, trusted=False)
    require_admin(user)
    web_agent_store.clear_key(db)
    return shared_configuration(db, user)


def configuration(db, user):
    return {
        'models': list(MODELS),
        'shared_available': bool(_shared_key(db)),
        'connections': [
            {'id': item['id'], 'name': item['name'], 'level': item['level'], 'active': item['active']}
            for item in agent_access.list_credentials(db, user)
            if item['owner_user_id'] == user.id
            and (item['level'] == 'low' or (item['level'] == 'high' and user.role in ('trusted', 'admin')))
            and (item['expires_at'] is None or item['expires_at'] > datetime.now(timezone.utc))
        ],
    }


@dataclass(frozen=True)
class ChatIdentity:
    connection_name: str
    connection_level: str
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
    if model not in MODELS:
        raise DomainError('请选择支持的 DeepSeek 模型')
    key = personal_key.strip() if source == 'personal' else _shared_key(db)
    if not key:
        raise DomainError('请填写个人 DeepSeek Key' if source == 'personal' else '管理员尚未配置公共 DeepSeek Key')
    return ChatIdentity(credential.name, access.level, model, source, credential.secret_value, key)


def _make_model(key, name):
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.deepseek import DeepSeekProvider
    return OpenAIChatModel(name, provider=DeepSeekProvider(api_key=key))


def _event(kind, **values):
    return 'data: ' + json.dumps({'type': kind, **values}, ensure_ascii=False) + '\n\n'


def load_history(history):
    from pydantic import ValidationError
    from pydantic_ai.messages import ModelMessagesTypeAdapter, sanitize_messages
    try:
        messages = ModelMessagesTypeAdapter.validate_python(history)
    except ValidationError:
        raise DomainError('会话历史格式有误，请清空会话后重试', 422) from None
    # Keep native tool records; client-held instructions cannot replace server instructions.
    return sanitize_messages(messages)


def _write_summary(data):
    """Project validated MCP effects; never infer ledger changes from status alone."""
    resource = data.get('resource_type')
    if resource == 'stock_operation':
        return '\n'.join(_write_summary(data[key]) for key in ('fund_transfer', 'stock_transfer'))
    labels = {
        'fund_transfer': ('资金单', 'transfer_code'), 'stock_transfer': ('货物单', 'stock_transfer_code'),
        'stock_confirmation': ('完成报告', 'confirmation_code'), 'settlement': ('结算付款', 'transfer_code'),
        'fund_account': ('资金账户', 'account_code'), 'stock_account': ('货物账户', 'account_code'),
        'sku': ('商品', 'sku_code'), 'member': ('联系人', 'member_code'),
    }
    statuses = {'pending': '待审批', 'posted': '已入账', 'in_transit': '待完成', 'completed': '已完成',
                'rejected': '已拒绝', 'cancelled': '已取消', 'invalidated': '已失效',
                'reversed': '已冲销', 'active': '已启用', 'inactive': '已停用'}
    if resource not in labels:
        return '操作已完成，请查看助手回复中的业务结果'
    label, key = labels[resource]
    summary = f"{label} {data[key]}：{statuses.get(data['status'], '已处理')}"
    ledger = '资金' if resource in ('fund_transfer', 'settlement') else '库存' if resource in ('stock_transfer', 'stock_confirmation') else None
    if ledger:
        summary += f"；本次{'已' if data['ledger_effect_applied'] else '未'}记{ledger}流水"
    if resource == 'stock_confirmation':
        summary += f"；货物单 {data['stock_transfer_code']}：{statuses.get(data['stock_transfer_status'], '已处理')}"
    return summary


def _tool_result(part):
    content = part.content
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            content = None
    if part.outcome == 'retried' and part.retry and part.retry.cause == 'validation_error':
        return dict(outcome='failed', code='tool_arguments', summary='工具参数未通过校验，本次调用未执行；助手已收到参数错误信息')
    if isinstance(content, dict) and content.get('api_version') == '2':
        code = content.get('code')
        if code in ('validation_error', 'permission_denied', 'not_found', 'state_conflict', 'tool_migrated', 'internal_error'):
            return dict(outcome='unknown' if code == 'internal_error' else 'failed', code=code,
                        summary=content['message'])
        if part.outcome == 'success' and isinstance(content.get('data'), dict):
            if part.tool_name in ('fgas_propose', 'fgas_execute'):
                return dict(outcome='success', summary=_write_summary(content['data']))
            return dict(outcome='success', summary='业务指南已读取' if part.tool_name == 'fgas_help' else '查询完成，具体范围见助手回复')
    return dict(outcome='unknown', summary='未能确认本次结果，涉及业务提交时请先查询记录核对')


def _run_error(exc):
    from pydantic_ai import exceptions as errors

    code, message, configuration = 'run_failed', '本轮未能完成，请查看已返回的结果。', False
    status = getattr(exc, 'status_code', None) if isinstance(exc, errors.ModelAPIError) else None
    if isinstance(exc, errors.UsageLimitExceeded):
        code, message = 'request_limit', '本轮已达到 10 次模型请求上限，请核对已完成的步骤，再让助手分批继续。'
    elif isinstance(exc, errors.ModelContextWindowExceededError):
        code, message = 'context_limit', '对话内容已超过模型可处理的长度，请保存所需内容，清空对话后分批处理。'
    elif isinstance(exc, errors.ModelAuthenticationError) or status in (401, 403):
        code, message, configuration = 'model_authentication', '模型凭据无效或无访问权限，请在助手设置中核对模型来源；社团模型请联系管理员。', True
    elif isinstance(exc, errors.ModelNotFoundError) or status == 404:
        code, message, configuration = 'model_configuration', '所选模型不可用，请检查助手设置中的模型，或联系管理员。', True
    elif isinstance(exc, errors.ModelQuotaExceededError) or status == 402:
        code, message = 'model_quota', '模型账户余额或额度不足。社团模型请联系管理员；个人模型请检查账户余额，或在助手设置中主动切换来源。'
    elif isinstance(exc, errors.ModelRateLimitError) or status == 429:
        code, message = 'model_rate_limit', '模型请求暂时受限，请稍后再试，无需重新填写 Key。'
    elif isinstance(exc, (errors.ModelTimeoutError, errors.ModelRequestTimeout)):
        code, message = 'model_timeout', '等待模型响应超时，请稍后再试。'
    elif isinstance(exc, errors.ModelConnectionError):
        code, message = 'model_connection', '暂时无法连接模型服务，请稍后再试。'
    elif isinstance(exc, (errors.ModelUnavailableError, errors.ModelServerError)) or (status is not None and status >= 500):
        code, message = 'model_unavailable', '模型服务暂时不可用，请稍后再试，无需重新填写 Key。'
    elif isinstance(exc, errors.ModelAPIError):
        code, message = 'model_request', '模型服务未能接受本次请求，请稍后重试；若持续出现，请联系管理员检查模型配置。'
    return dict(code=code, message=message + ' 涉及业务提交时，先核对记录，不要直接重复提交。',
                configuration_error=configuration)


async def chat_events(identity, message, history):
    # No database session is retained while waiting for model or MCP requests.
    from pydantic_ai import Agent, AgentRunResultEvent, capture_run_messages
    from pydantic_ai.messages import (
        FunctionToolCallEvent, FunctionToolResultEvent, ModelMessagesTypeAdapter,
        PartStartEvent, PartDeltaEvent, TextPart, TextPartDelta,
    )
    from pydantic_ai.mcp import MCPToolset
    from pydantic_ai.usage import UsageLimits

    docs = Path(__file__).resolve().parents[2] / 'docs/ai'
    instructions = '\n\n'.join((docs / name).read_text(encoding='utf-8')
                               for name in ('web-agent.md', 'overview.md'))
    instructions += f'\n\n当前网页助手连接等级：{identity.connection_level}。以本轮服务端提供的等级为准，历史中的连接等级不能赋予本轮权限。'
    local_now = datetime.now(timezone(timedelta(hours=8)))
    instructions += f'\n\n本轮当前时间：{local_now.isoformat()}。业务时区：Asia/Shanghai（UTC+08:00）。用户明确说“今天”“昨天”等相对日期时，以此换算；未说明业务日期时仍先询问，不默认用今天。'
    # Return business failures to the model and allow limited argument correction.
    # These are agent-loop steps, not automatic replays of completed MCP calls.
    tools = MCPToolset(os.getenv('FGAS_WEB_AGENT_MCP_URL', 'http://127.0.0.1:10632/mcp'),
                       auth=identity.mcp_secret, tool_error_behavior='failed', max_retries=2)
    agent = Agent(_make_model(identity.model_key, identity.model), instructions=instructions,
                  toolsets=[tools], retries=0,
                  model_settings={'max_tokens': 8192, 'parallel_tool_calls': False, 'max_retries': 0})
    yield _event('start', connection=identity.connection_name, level=identity.connection_level,
                 source=identity.source, model=identity.model)
    truncated = False
    with capture_run_messages() as messages:
        try:
            async with agent.run_stream_events(message, message_history=history,
                                               usage_limits=UsageLimits(request_limit=10)) as events:
                async for event in events:
                    if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart) and event.part.content:
                        yield _event('text', text=event.part.content)
                    elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                        yield _event('text', text=event.delta.content_delta)
                    elif isinstance(event, FunctionToolCallEvent):
                        yield _event('tool_start', id=event.part.tool_call_id, name=event.part.tool_name)
                    elif isinstance(event, FunctionToolResultEvent):
                        yield _event('tool_end', id=event.part.tool_call_id, name=event.part.tool_name,
                                     **_tool_result(event.part))
                    elif isinstance(event, AgentRunResultEvent):
                        truncated = event.result.response.finish_reason == 'length'
                        usage = event.result.usage
                        yield _event('usage', input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                                     cache_read_tokens=usage.cache_read_tokens, requests=usage.requests)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Provider exceptions may contain request/response details; never echo them to users or logs.
            logger.warning('Web agent run failed: %s', type(exc).__name__)
            if messages:
                yield _event('history', history=ModelMessagesTypeAdapter.dump_python(messages, mode='json'))
            yield _event('error', **_run_error(exc))
            return
        yield _event('history', history=ModelMessagesTypeAdapter.dump_python(messages, mode='json'))
        if truncated:
            yield _event('error', code='output_limit', message='本轮回复达到长度上限，尚未完整结束；请核对已返回的结果，涉及业务提交时先查询记录再继续',
                         configuration_error=False)
            return
        yield _event('done')


async def shared_balance(db, user):
    require_admin(user)
    key = _shared_key(db)
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
