"""Fixed MCP contracts shared by discovery, on-demand help and input validation."""
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError, create_model

from backend.application import agent_operations as ops, agent_queries as queries
from backend.application import stocktakes
from backend.entrypoints import agent_schemas as schemas
from backend.entrypoints.schemas import Input
from backend.kernel.accounting import DomainError


@dataclass(frozen=True)
class Contract:
    handler: Callable
    summary: str
    example: dict
    input_model: type[BaseModel]
    output_model: type[BaseModel]


def contract(handler, summary, example):
    name = handler.__name__
    inputs = schemas.QUERY_INPUT_SCHEMAS | schemas.OPERATION_INPUT_SCHEMAS
    outputs = schemas.QUERY_OUTPUT_SCHEMAS | schemas.OPERATION_OUTPUT_SCHEMAS
    return Contract(handler, summary, example, inputs[name], outputs[name])


FUND = dict(source_account_code='FA-0001', destination_account_code='FA-0002',
            amount='120.50', effective_date='2026-10-22', description='用户说明的实际用途')
STOCK = dict(source_account_code='SA-0001', destination_account_code='SA-0002',
             effective_date='2026-10-22', lines=[dict(sku_code='ARC-01-A', quantity='2')])
COMPLETION = dict(identifier='ST-000001', effective_date='2026-10-22')
ALLOCATION = [dict(item_transfer_code='FT-000002', amount='120.50')]

QUERIES = {
    'me': contract(queries.me, '查看当前真实登录用户的名称、角色，以及本连接名称和执行等级；返回单对象，不接受查询条件。', {}),
    'fund_accounts': contract(queries.list_fund_accounts, '查资金账户及其公私分类、联系人和标签。', {'q': '公账', 'active': True}),
    'stock_accounts': contract(queries.list_stock_accounts, '查货物账户及 member_code/member_name 当前负责人；按 member_code 筛选，identifier 详情含负责人历史。', {'q': '仓库', 'active': True}),
    'skus': contract(queries.list_skus, '按业务SKU代号code精确查询，q搜代号/完整名称，tag筛选类别或角色；返回code、名称、标签和整数单位。', {'code': 'ARC-01-A'}),
    'members': contract(queries.list_members, '查业务联系人名称及 note 备注。', {'q': '小王'}),
    'fund_balances': contract(queries.get_fund_balances, '查账面余额；total 始终为全部公账合计，不是筛选行合计；支持 as_of/basis 查截止时点。余额不是收入、费用或利润。', {'kind': 'public', 'as_of': '2026-10-01T00:00:00+08:00', 'basis': 'posted'}),
    'inventory': contract(queries.get_inventory, '按sku_code查正式库存及待完成流入/流出；计划仅含已批准尚未确认完成。account_code/member_code筛选账户范围；totals逐SKU汇总正式数量及外部流入、对外流出、内部调拨，任一端涉及范围的明细只计一次。分页重复返回同一筛选范围汇总，不可相加。as_of/basis查历史正式库存，历史计划为null，不提供估值。', {'sku_code': 'BAD-01-A'}),
    'fund_transfers': contract(queries.list_fund_transfers, '按条件查资金转移；默认最近30天，全量传 all_time=true；支持 identifier 查详情。资金流动不能直接当作经营收入费用或利润；代收交回是结算，不重复计为新增营业收入。', {'status': 'pending'}),
    'stock_transfers': contract(queries.list_stock_transfers, '按sku_code等条件查货物转移；默认最近30天，全量传all_time=true；完成报告在父单详情的完成记录中。', {'status': 'in_transit', 'sku_code': 'BAD-01-A'}),
    'stock_moves': contract(queries.list_stock_moves, '按sku_code查正式数量流水；默认最近30天，全量传all_time=true。', {'sku_code': 'BAD-01-A', 'all_time': True}),
    'settlement_overview': contract(queries.get_settlement_overview, '查一个私账的逐笔收支未结、付款及匹配；不从净余额推断，也不把单个私账结算当作整场经营核算。', {'identifier': 'FA-0003'}),
    'settlement_outstanding': contract(queries.list_settlement_outstanding, '跨私账查全部已过账未匹配记录，不限30天；kind=item 原收支、payment 结算付款，direction=expense 报销、receipt 交回。仅含未匹配项，不是全量经营收入费用；两侧金额不可相加为待付款额；匹配仍仅 high。', {'direction': 'expense', 'page': 1, 'limit': 20}),
    'fund_stocktakes': contract(queries.list_fund_stocktakes, '查资金盘点；支持 identifier 查专属端点关联记录。', {'status': 'in_progress'}),
    'stock_stocktakes': contract(queries.list_stock_stocktakes, '查货物盘点；结束不表示账目已自动调整。', {'status': 'in_progress'}),
}
DETAILS = {
    'settlement_overview': QUERIES['settlement_overview'],
    'stock_accounts': contract(queries.get_stock_account, '返回货物账户和 responsibility_history 负责人历史，含起止时间及操作人；负责人变化不改变库存。', {'identifier': 'SA-0001'}),
    'fund_transfers': contract(queries.get_fund_transfer, '返回资金单、正式分录、审批及审计。', {'identifier': 'FT-000001'}),
    'stock_transfers': contract(queries.get_stock_transfer, '返回货物单及 confirmations；按申请编号 SC 分辨各申请状态。', {'identifier': 'ST-000001'}),
    'fund_stocktakes': contract(queries.get_fund_stocktake, '返回资金盘点及关联转移，包含更正和各状态。', {'identifier': 'fund-stocktake-id'}),
    'stock_stocktakes': contract(queries.get_stock_stocktake, '返回货物盘点及关联转移，包含更正和各状态。', {'identifier': 'stock-stocktake-id'}),
}
PROPOSALS = {
    'fund_transfer': contract(ops.propose_fund_transfer, '提交资金待审申请，不产生资金分录；high 调用也待审。', FUND),
    'stock_transfer': contract(ops.propose_stock_transfer, '提交货物待审申请，不改变库存；批准后仍须确认完成。', STOCK),
    'stock_completion': contract(ops.propose_stock_completion, '报告整笔转移已完成、等待核实时使用；identifier 是父货物单编号 ST。返回待确认完成报告，主单仍待完成且库存不变；high 的 propose 也待确认。报告状态查父单详情的 confirmations。', COMPLETION),
}
EXECUTIONS = {
    'fund_account': {
        'create': contract(ops.create_fund_account, '创建资金账户，不改变余额；kind 创建后固定。', {'name': '小王私账', 'kind': 'private'}),
        'update': contract(ops.update_fund_account, '修改指定字段；省略保留原值，允许清空的字段才可传 null。', {'identifier': 'FA-0001', 'name': '新的账户名称'}),
    },
    'stock_account': {
        'create': contract(ops.create_stock_account, '创建货物账户：internal 实际保管、external 外部；member_code 可指定负责人并记录历史，不改变库存。', {'name': '主仓库', 'kind': 'internal'}),
        'update': contract(ops.update_stock_account, '修改货物资料或负责人；member_code 省略保留、null 清空，变更自动留历史，不改变库存。', {'identifier': 'SA-0001', 'member_code': 'M-0001'}),
    },
    'sku': {
        'create': contract(ops.create_sku, '创建唯一业务SKU代号、完整商品名称及标签，不增加库存；code去空格转大写，重复拒绝。', {'code': 'ARC-01-A', 'name': '博丽灵梦立牌 10cm 春服A款', 'unit': '个', 'tags': ['类别:立牌', '角色:博丽灵梦']}),
        'update': contract(ops.update_sku, 'identifier填业务SKU代号；修改资料，已使用SKU的单位不可变更。', {'identifier': 'ARC-01-A', 'name': '博丽灵梦立牌 10cm 春服A款'}),
    },
    'member': {
        'create': contract(ops.create_member, '创建业务联系人，不创建登录用户或自动开账。', {'name': '小王'}),
        'update': contract(ops.update_member, '修改联系人资料，不转移账户债务或授予权限。', {'identifier': 'M-0001', 'note': '用户提供的联系说明'}),
    },
    'fund_transfer': {
        'create': contract(ops.create_fund_transfer, '直接登记并过账，产生资金分录；不发起实际银行付款。', FUND),
        'approve': contract(ops.approve_fund_transfer, '批准待审资金单并过账；expected_version 填资金单详情的 version。', {'identifier': 'FT-000001', 'expected_version': 1}),
        'reject': contract(ops.reject_fund_transfer, '拒绝待审资金单，保留原因；不产生分录。', {'identifier': 'FT-000001', 'expected_version': 1, 'reason': '用户说明的拒绝原因'}),
        'reverse': contract(ops.reverse_fund_transfer, '以反向资金记录更正已过账单，保留原单；不自动退款或退货。', {'identifier': 'FT-000001', 'reason': '用户说明的更正原因'}),
    },
    'stock_transfer': {
        'create': contract(ops.create_stock_transfer, '登记获批待完成的货物单，库存不变；fund_transfer_codes 可关联已有付款，建单后也可用 link_fund 补充。到货后另行 complete。', STOCK),
        'approve': contract(ops.approve_stock_transfer, '批准转移后主单待完成，库存不变。', {'identifier': 'ST-000001'}),
        'reject': contract(ops.reject_stock_transfer, '拒绝待审货物单，保留原因。', {'identifier': 'ST-000001', 'reason': '用户说明的拒绝原因'}),
        'cancel': contract(ops.cancel_stock_transfer, '取消可取消的货物单，不自动退款；已完成货物须新增更正转移。', {'identifier': 'ST-000001', 'reason': '用户说明的取消原因'}),
        'complete': contract(ops.complete_stock_transfer, '用户已确认整笔到货并授权直接登记时使用；identifier 是父货物单编号 ST。新建并完成确认，立即记库存。返回 stock_confirmation：confirmation_code/status 属于确认，stock_transfer_code/stock_transfer_status 属于父单。已有待确认完成报告时应 approve 该报告。', COMPLETION),
        'link_fund': contract(ops.add_stock_fund_reference, '引用已有资金单，不新建付款或改变库存。', {'identifier': 'ST-000001', 'fund_transfer_code': 'FT-000001'}),
    },
    'stock_completion': {
        'approve': contract(ops.approve_stock_completion, '核实并确认已有完成报告后记库存；identifier 填父货物单详情 confirmations 中的报告编号 SC，无需再执行 stock_transfer/complete。', {'identifier': 'SC-000001'}),
        'reject': contract(ops.reject_stock_completion, '退回完成报告；identifier 是报告编号 SC，父单仍待完成。', {'identifier': 'SC-000001', 'reason': '用户说明的拒绝原因'}),
    },
    'settlement': {
        'create': contract(ops.create_settlement, '新记一笔结算付款并匹配原收支；已有付款应使用 match。', {'transfer': FUND, 'allocations': ALLOCATION}),
        'match': contract(ops.add_settlement_matches, '给已有结算付款追加匹配，不再次记钱；identifier 是付款单编号 FT。', {'identifier': 'FT-000003', 'allocations': ALLOCATION}),
    },
    'stock_operation': {
        'create': contract(ops.create_stock_operation, '同一事务新建付款和货物单：付款过账，货物待完成；已有付款用引用。', {'stock': STOCK, 'money': FUND}),
    },
    'fund_stocktake': {
        'create': contract(ops.create_fund_stocktake, '创建资金盘点和专属盈亏账户；不调整余额。', {'name': '月末资金盘点'}),
        'update': contract(ops.update_fund_stocktake, '修改盘点说明，账目调整使用普通资金转移。', {'identifier': 'fund-stocktake-id', 'description': '用户提供的核对结果'}),
        'end': contract(ops.end_fund_stocktake, '结束资金盘点的整理状态，不自动结清差异。', {'identifier': 'fund-stocktake-id'}),
    },
    'stock_stocktake': {
        'create': contract(ops.create_stock_stocktake, '创建货物盘点和专属盈亏账户；不调整库存。', {'name': '月末库存盘点'}),
        'update': contract(ops.update_stock_stocktake, '修改盘点说明，实点差异使用普通货物转移。', {'identifier': 'stock-stocktake-id', 'description': '用户提供的实点结果'}),
        'end': contract(ops.end_stock_stocktake, '结束货物盘点的整理状态，不自动调整库存。', {'identifier': 'stock-stocktake-id'}),
    },
}


# Keep the dormant contracts above so stocktakes can be restored with their code.
if not stocktakes.ENABLED:
    QUERIES = {key: value for key, value in QUERIES.items() if key not in ('fund_stocktakes', 'stock_stocktakes')}
    DETAILS = {key: value for key, value in DETAILS.items() if key not in ('fund_stocktakes', 'stock_stocktakes')}
    EXECUTIONS = {key: value for key, value in EXECUTIONS.items() if key not in ('fund_stocktake', 'stock_stocktake')}

Resource = Literal[tuple(dict.fromkeys([*QUERIES, *PROPOSALS, *EXECUTIONS]))]
Action = Literal[tuple(sorted({action for actions in EXECUTIONS.values() for action in actions}))]


class HelpInput(Input):
    topic: Literal['overview', 'guide', 'query', 'propose', 'execute'] = 'overview'
    resource: Resource | None = None
    action: Action | None = None
    include_output_schema: bool = Field(default=False, description='仅查看具体操作时使用；true 额外返回完整输出 Schema。')


QueryInput = create_model('QueryInput', __base__=Input,
    resource=(Literal[tuple(QUERIES)], Field(description='要查询的业务对象；参数不确定时用 fgas_help(topic=query, resource=...)。')),
    identifier=(str | None, Field(default=None, min_length=1, description='货物账户、资金和货物转移用于查详情；settlement_overview 用于指定私账。不能附非空 filters。')),
    filters=(dict[str, Any], Field(default_factory=dict, description='该对象实际支持的过滤字段；事件列表默认最近30天，全量传 all_time=true；余额/库存支持 as_of/basis；按需查 help，不支持的字段会被拒绝。')))
ProposeInput = create_model('ProposeInput', __base__=Input,
    resource=(Literal[tuple(PROPOSALS)], ...),
    data=(dict[str, Any], Field(description='该申请的精确业务参数，参见 fgas_help(topic=propose, resource=...)。')))
ExecuteInput = create_model('ExecuteInput', __base__=Input,
    resource=(Literal[tuple(EXECUTIONS)], ...),
    action=(Action, ...),
    data=(dict[str, Any], Field(description='按对象/动作校验的参数；仅变更指定字段，需要业务编号时使用 data.identifier。')))
PUBLIC_INPUTS = {'fgas_help': HelpInput, 'fgas_query': QueryInput,
                 'fgas_propose': ProposeInput, 'fgas_execute': ExecuteInput}
TOOL_DESCRIPTIONS = {
    'fgas_help': '首次使用先无参调用，了解账本模型和当前权限；按 topic/resource/action 查输入参数与示例。已知用法无需重复查。',
    'fgas_query': '读取业务资料。首次使用先 fgas_help()；identifier 查详情，filters 查列表。事件默认近30天，全量传 all_time=true；has_more=true 继续翻页。',
    'fgas_propose': '提交资金、货物申请或整笔完成报告，high 也始终待审、不记正式流水。首次使用先 fgas_help()，参数查 topic=propose。',
    'fgas_execute': '仅 high 直接办理业务。首次使用先 fgas_help()，具体参数查 topic=execute；资金创建过账，货物创建后待完成，确认整笔完成才记库存。',
}


def help_call(topic, resource=None, action=None):
    arguments = dict(topic=topic)
    if resource is not None:
        arguments['resource'] = resource
    if action is not None:
        arguments['action'] = action
    return dict(tool='fgas_help', arguments=arguments)


class InputProblem(DomainError):
    def __init__(self, fields, help_request):
        self.fields, self.help_request = fields, help_request
        super().__init__('参数有误：' + '；'.join(f"{field['field']}：{field['message']}" for field in fields))


def invalid(field, message, hint):
    raise InputProblem([dict(field=field, message=message)], hint)


def validate(model, values, hint, prefix=''):
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        messages = {'missing': '必须填写', 'extra_forbidden': '此操作不支持该字段'}
        fields = []
        for error in exc.errors(include_url=False, include_context=False, include_input=False):
            message = messages.get(error['type'], error['msg'])
            if error['type'] == 'extra_forbidden' and len(error['loc']) == 1 and model.model_fields:
                message += '；可用字段：' + '、'.join(model.model_fields)
            fields.append(dict(
                field='.'.join(filter(None, [prefix, *map(str, error['loc'])])) or 'arguments',
                message=message,
            ))
        raise InputProblem(fields, hint) from exc


def select_write(topic, resource, action=None):
    table = PROPOSALS if topic == 'propose' else EXECUTIONS
    if resource not in table:
        invalid('resource', '请选择该入口支持的对象', help_call(topic))
    if topic == 'propose':
        if action is not None:
            invalid('action', '提议不接收 action', help_call(topic, resource))
        return table[resource]
    if action not in table[resource]:
        invalid('action', '该对象支持：' + ', '.join(table[resource]), help_call(topic, resource))
    return table[resource][action]


def prepare_call(tool, arguments):
    """Validate the full call before invoking an application service."""
    topic = tool.removeprefix('fgas_')
    request = validate(PUBLIC_INPUTS[tool], arguments, help_call(topic))
    resource = request.resource
    if tool == 'fgas_query':
        hint = help_call('query', resource)
        if request.identifier is not None:
            if resource not in DETAILS:
                invalid('identifier', '该对象不支持按业务编号查询详情，请使用 filters', hint)
            if request.filters:
                invalid('filters', '详情查询不能同时提供过滤条件', hint)
            selected, values, prefix = DETAILS[resource], {'identifier': request.identifier}, ''
        else:
            if resource == 'settlement_overview': invalid('identifier', '请提供私账业务编号 FA', hint)
            selected, values, prefix = QUERIES[resource], request.filters, 'filters'
    else:
        action = getattr(request, 'action', None)
        hint = help_call(topic, resource, action)
        selected, values, prefix = select_write(topic, resource, action), request.data, 'data'
    parsed = validate(selected.input_model, values, hint, prefix)
    return selected, parsed.model_dump(mode='json', exclude_unset=selected.handler.__name__.startswith('update_'))


def describe(topic, resource, selected, action=None, detail=False, *, include_output_schema=False):
    """Generate an exact, executable call schema only for the requested operation."""
    fields = {'resource': (Literal[resource], ...)}
    if topic == 'query':
        if resource == 'me':
            example = dict(resource=resource)
        elif detail:
            fields['identifier'] = (str, Field(min_length=1))
            example = dict(resource=resource, **selected.example)
        else:
            required = any(field.is_required() for field in selected.input_model.model_fields.values())
            fields['filters'] = (selected.input_model, ... if required else Field(default_factory=selected.input_model))
            example = dict(resource=resource, filters=selected.example)
    else:
        if action is not None:
            fields['action'] = (Literal[action], ...)
        fields['data'] = (selected.input_model, ...)
        example = dict(resource=resource, data=selected.example)
        if action is not None:
            example['action'] = action
    model = create_model('OperationInput', __base__=Input, **fields)
    result = dict(summary=selected.summary, input_schema=model.model_json_schema(), example=example)
    if include_output_schema:
        result['output_schema'] = selected.output_model.model_json_schema()
    return result


def help_data(level, *, topic, resource=None, action=None, include_output_schema=False):
    """On-demand contracts, independent of any client discovery implementation."""
    if topic == 'execute' and level != 'high':
        raise DomainError('当前连接只能查询或提交待审申请，不能直接办理。后续可由具备相应权限的人工登录网页办理，或由用户已授权的 high Agent 使用合法 high MCP 连接办理。', 403)
    if topic not in ('query', 'propose', 'execute'):
        invalid('topic', '请选择 query、propose 或 execute 查看契约', help_call('overview'))
    if topic != 'execute' and action is not None:
        invalid('action', '仅 execute 帮助接收 action', help_call(topic, resource))
    if include_output_schema and (resource is None or (topic == 'execute' and action is None)):
        invalid('include_output_schema', '请先选定 resource；execute 还须指定 action', help_call(topic, resource))
    if resource is None:
        if action is not None:
            invalid('resource', '指定动作时也须指定对象', help_call(topic))
        if topic == 'execute':
            return dict(resources=[dict(resource=name, actions={action: item.summary for action, item in actions.items()}) for name, actions in EXECUTIONS.items()])
        table = QUERIES if topic == 'query' else PROPOSALS
        return dict(resources=[dict(resource=name, summary=item.summary) for name, item in table.items()])
    if topic == 'query':
        if resource not in QUERIES:
            invalid('resource', '未知查询对象', help_call(topic))
        if resource in ('me', 'settlement_overview'):
            return dict(resource=resource, object=describe(topic, resource, QUERIES[resource], detail=resource == 'settlement_overview', include_output_schema=include_output_schema))
        result = dict(resource=resource, list=describe(topic, resource, QUERIES[resource], include_output_schema=include_output_schema))
        if resource in DETAILS:
            result['detail'] = describe(topic, resource, DETAILS[resource], detail=True, include_output_schema=include_output_schema)
        return result
    if topic == 'execute' and action is None:
        if resource not in EXECUTIONS:
            invalid('resource', '未知执行对象', help_call(topic))
        return dict(resource=resource, actions={name: item.summary for name, item in EXECUTIONS[resource].items()})
    return describe(topic, resource, select_write(topic, resource, action), action, include_output_schema=include_output_schema)
