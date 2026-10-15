"""Official Streamable HTTP adapter; business authority is resolved per request/call."""
from contextlib import contextmanager
from contextvars import ContextVar
import inspect
import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool, ToolAnnotations, CallToolResult, TextContent
from pydantic import ValidationError
from starlette.responses import JSONResponse

from backend.application import agent_access, agent_queries, agent_operations
from backend.entrypoints.agent_schemas import (
    QUERY_INPUT_SCHEMAS, QUERY_OUTPUT_SCHEMAS,
    OPERATION_INPUT_SCHEMAS, OPERATION_OUTPUT_SCHEMAS, ContextInput, ContextOutput,
)
from backend.infrastructure import store
from backend.kernel.accounting import DomainError

_bearer: ContextVar[str | None] = ContextVar('fgas_mcp_bearer', default=None)
GUIDE = (Path(__file__).resolve().parents[2] / 'docs/ai/guide.md').read_text()
GUIDE_VERSION = 'draft-2026-10-15-r5'
INPUTS = {**QUERY_INPUT_SCHEMAS, **OPERATION_INPUT_SCHEMAS, 'get_context': ContextInput}
OUTPUTS = {**QUERY_OUTPUT_SCHEMAS, **OPERATION_OUTPUT_SCHEMAS, 'get_context': ContextOutput}
COMMON = frozenset(QUERY_INPUT_SCHEMAS) | {
    'propose_fund_transfer', 'propose_stock_transfer', 'propose_stock_completion', 'get_context'}


@contextmanager
def business_session():
    # Reuse the HTTP transaction generator, including commit and rollback behavior.
    with contextmanager(store.transaction)() as db:
        yield db


def available_tools(access):
    return ['fgas_' + name for name in INPUTS if access.level == 'high' or name in COMMON]


def get_context(access: agent_access.AgentAccess) -> dict:
    return dict(api_version='1', guide_version=GUIDE_VERSION, guide=GUIDE,
                level=access.level, available_tools=available_tools(access),
                semantics=dict(currency='CNY', amount_input='yuan decimal string',
                               business_date='YYYY-MM-DD; inclusive date filters',
                               created_at='timezone-aware ISO; start inclusive, end exclusive',
                               pagination='page/limit/has_more; one page is not all records',
                               proposals='always pending; no ledger effect until approved',
                               stock='in_transit is planned movement; completion changes inventory',
                               patch='omitted fields unchanged; explicit null only when allowed',
                               human_management='users, roles and credentials are human managed',
                               uncertain_result='query records before manual retry; writes are not deduplicated'))


def _result(data, *, error=False):
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(data, ensure_ascii=False))],
                          structured_content=data, is_error=error)


class FGASMCPServer(MCPServer):
    async def list_tools(self):
        with business_session() as db:
            access = agent_access.resolve(db, _bearer.get())
            names = available_tools(access)
        return [Tool(name=name, description=(
            '读取当前连接与业务操作指南' if name == 'fgas_get_context' else
            name.removeprefix('fgas_').replace('_', ' ')),
            input_schema=INPUTS[name[5:]].model_json_schema(),
            output_schema=OUTPUTS[name[5:]].model_json_schema(),
            annotations=ToolAnnotations(read_only_hint=name[5:] in QUERY_INPUT_SCHEMAS or name == 'fgas_get_context'))
            for name in names]

    async def call_tool(self, name, arguments, context=None):
        try:
            with business_session() as db:
                access = agent_access.resolve(db, _bearer.get())
                key = name.removeprefix('fgas_')
                if not name.startswith('fgas_') or key not in INPUTS:
                    raise DomainError('工具不存在', 404)
                # Application operations also guard high authority themselves.
                if key not in COMMON:
                    agent_access.require_high(access)
                values = INPUTS[key].model_validate(arguments).model_dump(
                    mode='json', exclude_unset=key.startswith('update_'))
                if key == 'get_context':
                    data = get_context(access)
                else:
                    module = agent_queries if key in QUERY_INPUT_SCHEMAS else agent_operations
                    fn = getattr(module, key)
                    if 'identifier' in inspect.signature(fn).parameters:
                        identifier = values.pop('identifier')
                        data = fn(db, access, identifier, values) if module is agent_operations else fn(db, access, identifier)
                    else:
                        data = fn(db, access, values)
                data = OUTPUTS[key].model_validate(data).model_dump(mode='json')
            return _result(data)
        except ValidationError:
            return _result(dict(code='validation_error', message='参数或结果不符合工具声明，请核对字段及格式'), error=True)
        except DomainError as exc:
            code = {401: 'permission_denied', 403: 'permission_denied', 404: 'not_found',
                    409: 'state_conflict'}.get(exc.status, 'validation_error')
            return _result(dict(code=code, message=str(exc)), error=True)
        except Exception:
            return _result(dict(code='state_conflict', message='操作未能完成，请查询记录并联系管理员核对'), error=True)


class BearerAuth:
    def __init__(self, app, server):
        self.app, self.server = app, server
        self.session_manager = server.session_manager

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = [value.decode('latin-1') for key, value in scope.get('headers', []) if key.lower() == b'authorization']
        parts = headers[0].split() if len(headers) == 1 else []
        secret = parts[1] if len(parts) == 2 and parts[0].lower() == 'bearer' else None
        try:
            with business_session() as db:
                agent_access.resolve(db, secret)
        except DomainError as exc:
            response = JSONResponse({'code': 'permission_denied', 'message': str(exc)},
                                    status_code=exc.status, headers={'WWW-Authenticate': 'Bearer'})
            return await response(scope, receive, send)
        token = _bearer.set(secret)
        try:
            await self.app(scope, receive, send)
        finally:
            _bearer.reset(token)


def create_mcp_app():
    server = FGASMCPServer('FGAS', version='1', instructions='先调用 fgas_get_context 阅读业务指南。')
    transport = server.streamable_http_app(streamable_http_path='/mcp', stateless_http=True, json_response=True)
    return BearerAuth(transport, server)
