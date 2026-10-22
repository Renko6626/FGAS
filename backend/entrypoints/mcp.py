"""Compact Streamable HTTP adapter; business authority is resolved per call."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool, ToolAnnotations, CallToolResult, TextContent
from pydantic import ValidationError
from starlette.responses import JSONResponse

from backend.application import agent_access
from backend.entrypoints import agent_catalog as catalog
from backend.entrypoints.agent_schemas import QueryResult
from backend.infrastructure import store
from backend.kernel.accounting import DomainError

_bearer: ContextVar[str | None] = ContextVar('fgas_mcp_bearer', default=None)
_DOCS = Path(__file__).resolve().parents[2] / 'docs/ai'
GUIDE = (_DOCS / 'guide.md').read_text()
OVERVIEW = (_DOCS / 'overview.md').read_text()
GUIDE_VERSION = '2026-10-22-v2'
RESULT_SCHEMA = QueryResult[dict].model_json_schema()
logger = logging.getLogger(__name__)
LEGACY_TOOLS = {'fgas_get_context'} | {
    'fgas_' + name for name in catalog.schemas.QUERY_INPUT_SCHEMAS | catalog.schemas.OPERATION_INPUT_SCHEMAS
}


@contextmanager
def business_session():
    with contextmanager(store.transaction)() as db:
        yield db


def available_tools(access):
    return [name for name in catalog.PUBLIC_INPUTS if name != 'fgas_execute' or access.level == 'high']


def get_help(access, arguments):
    request = catalog.validate(catalog.HelpInput, arguments, catalog.help_call('overview'))
    if request.topic not in ('overview', 'guide'):
        return catalog.help_data(access.level, **request.model_dump())
    if request.resource is not None or request.action is not None:
        catalog.invalid('topic', 'overview/guide 不接收 resource 或 action；请选 query/propose/execute', catalog.help_call('overview'))
    if request.topic == 'guide':
        return dict(guide_version=GUIDE_VERSION, guide=GUIDE)
    capabilities = dict(query=list(catalog.QUERIES), propose=list(catalog.PROPOSALS))
    if access.level == 'high':
        capabilities['execute'] = {resource: list(actions) for resource, actions in catalog.EXECUTIONS.items()}
    return dict(guide_version=GUIDE_VERSION, level=access.level, model=OVERVIEW,
                available_tools=available_tools(access), capabilities=capabilities)


def _result(data, *, error=False):
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(data, ensure_ascii=False))],
                          structured_content=data, is_error=error)


class FGASMCPServer(MCPServer):
    async def list_tools(self):
        with business_session() as db:
            names = available_tools(agent_access.resolve(db, _bearer.get()))
        return [Tool(name=name, description=catalog.TOOL_DESCRIPTIONS[name],
                     input_schema=catalog.PUBLIC_INPUTS[name].model_json_schema(),
                     output_schema=RESULT_SCHEMA,
                     annotations=ToolAnnotations(read_only_hint=name in ('fgas_help', 'fgas_query')))
                for name in names]

    async def call_tool(self, name, arguments, context=None):
        try:
            with business_session() as db:
                access = agent_access.resolve(db, _bearer.get())
                if name in LEGACY_TOOLS:
                    return _result(dict(api_version='2', code='tool_migrated',
                        message='此工具已被 MCP v2 四入口替代。请重新发现工具并调用 fgas_help；旧工具未执行任何业务。',
                        help=catalog.help_call('overview')), error=True)
                if name not in catalog.PUBLIC_INPUTS:
                    raise DomainError('工具不存在，请调用 fgas_help 查看用法', 404)
                if name == 'fgas_execute':
                    agent_access.require_high(access)
                if name == 'fgas_help':
                    data = dict(api_version='2', data=get_help(access, arguments))
                else:
                    selected, values = catalog.prepare_call(name, arguments)
                    fn = selected.handler
                    if 'identifier' in selected.input_model.model_fields:
                        identifier = values.pop('identifier')
                        data = fn(db, access, identifier) if name == 'fgas_query' else fn(db, access, identifier, values)
                    else:
                        data = fn(db, access, values)
                    # Validate before leaving the transaction: malformed results roll back writes.
                    data = selected.output_model.model_validate(data).model_dump(mode='json')
            return _result(data)
        except catalog.InputProblem as exc:
            return _result(dict(api_version='2', code='validation_error', message=str(exc),
                                fields=exc.fields, help=exc.help_request), error=True)
        except ValidationError:
            logger.exception('FGAS operation returned an invalid result')
            return _result(dict(api_version='2', code='internal_error',
                message='服务端返回结果不符合契约，本次事务已回滚；请联系管理员核对。'), error=True)
        except DomainError as exc:
            code = {401: 'permission_denied', 403: 'permission_denied', 404: 'not_found',
                    409: 'state_conflict'}.get(exc.status, 'validation_error')
            return _result(dict(api_version='2', code=code, message=str(exc)), error=True)
        except Exception:
            logger.exception('FGAS operation failed')
            return _result(dict(api_version='2', code='internal_error',
                message='操作未能完成，请查询记录并联系管理员核对；不要自动重发写入。'), error=True)


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
    server = FGASMCPServer('FGAS', version='2', instructions=OVERVIEW)
    transport = server.streamable_http_app(streamable_http_path='/mcp', stateless_http=True, json_response=True)
    return BearerAuth(transport, server)
