"""Stock plans and approval; formal quantities are created only by completion."""
from datetime import date
from typing import Literal
from backend.application.agent_access import AgentAccess, auto_apply, require_operator, source_fields, operation_fields
from backend.infrastructure import store, stock_store
from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit, now
from backend.application.identity import authorize_write
from backend.application import warehouse_catalogs
from backend.application.directory_views import by_code
from backend.infrastructure.models import StockAccount, Transfer
from backend.kernel.accounting import DomainError
from backend.kernel.stock import parse_quantity, quantity_string
from backend.modules.warehouse.plans import build_moves
from backend.infrastructure.models import StockConfirmation, StockMove


def get_transfer(db, identifier):
    item = by_code(db, StockTransfer, identifier)
    return item


def validate(db,data,existing=False):
    source_id,destination_id=data['source_account_id'],data['destination_account_id']
    if source_id==destination_id: raise DomainError('来源与去向不能相同')
    accounts=[store.get_stock_account(db,i) for i in (source_id,destination_id)]
    if any(a is None for a in accounts): raise DomainError('账户不存在',404)
    if not existing and any(not a.active for a in accounts): raise DomainError('账户已停用',409)
    if all(a.kind=='external' for a in accounts): raise DomainError('不能在两个外部账户间转移')
    if data.get('related_transfer_id') and stock_store.get_transfer(db,data['related_transfer_id']) is None: raise DomainError('关联货物单不存在',404)
    identifiers=[line['sku_id'] for line in data['lines']]
    if not identifiers or len(set(identifiers))!=len(identifiers): raise DomainError('SKU 明细不能为空或重复')
    lines=[]
    for line in data['lines']:
        sku=stock_store.get_sku(db,line['sku_id'])
        if sku is None: raise DomainError('SKU 不存在',404)
        if not existing and not sku.active: raise DomainError('SKU 已停用',409)
        lines.append(dict(sku_id=sku.id,quantity=parse_quantity(line['quantity'])))
    funds=data.get('fund_transfer_ids',[])
    if len(set(funds))!=len(funds): raise DomainError('资金引用不能重复')
    if any(store.get_transfer(db,i) is None for i in funds): raise DomainError('资金引用不存在',404)
    return lines

def transfer_view(db, item, *, detail=True):
    value = {key: getattr(item, key) for key in ('code','effective_date','description','tags','source_reference','actor_id','status','approved_by','approval_mode','reason','created_at','submitted_credential_id','submitted_credential_name')}
    for side in ('source', 'destination'):
        account = store.get_stock_account(db, getattr(item, side + '_account_id'))
        value[side + '_account_name'] = account.name
        value[side + '_account_code'] = account.code
        value[side + '_kind'] = account.kind
    value['related_transfer_code'] = stock_store.get_transfer(db,item.related_transfer_id).code if item.related_transfer_id else None
    value['lines'] = []
    for line in stock_store.lines(db, item.id):
        sku = stock_store.get_sku(db, line.sku_id)
        value['lines'].append(dict(sku_code=sku.code, sku_name=sku.name, unit=sku.unit, quantity=quantity_string(line.quantity)))
    value['snapshot_at'] = now()
    if not detail:
        return value
    value['confirmations'] = [confirmation_view(db,c) for c in stock_store.confirmations(db, item.id)]
    value['fund_references'] = []
    for reference in stock_store.fund_references(db, item.id):
        fund = store.get_transfer(db, reference.fund_transfer_id)
        value['fund_references'].append(dict(code=fund.code,status=fund.status,description=fund.description,
            amount_minor=fund.amount_minor,reversal_of_code=store.get_transfer(db,fund.reversal_of).code if fund.reversal_of else None,
            source_account_code=store.get_account(db,fund.source_account_id).code,
            destination_account_code=store.get_account(db,fund.destination_account_id).code))
    value['related_transfers']=[dict(code=a.code,status=a.status,
        source_account_code=store.get_stock_account(db,a.source_account_id).code,
        destination_account_code=store.get_stock_account(db,a.destination_account_id).code,
        lines=[dict(sku_code=stock_store.get_sku(db,l.sku_id).code,quantity=quantity_string(l.quantity)) for l in stock_store.lines(db,a.id)]) for a in stock_store.related_transfers(db,item.id)]
    value['audit'] = [dict(actor_id=a.actor_id, action=a.action, detail=a.detail, created_at=a.created_at, agent_credential_id=a.agent_credential_id, agent_credential_name=a.agent_credential_name) for a in stock_store.audit_events(db, item.id)]
    return value


def audit(db, item, user, action, detail, *, access=None):
    stock_store.create(db, StockAudit, dict(stock_transfer_id=item.id, actor_id=user.id, action=action, detail=detail) | operation_fields(access))


def approve(db, item, user, mode, *, access=None):
    require_operator(user, access)
    validate(db, business_data(db, item),existing=True)
    item.approved_by, item.approval_mode = user.id, mode
    item.status = 'in_transit'


def submit_transfer(db, user, data, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    authorize_write(db, user, trusted=False)
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    data = data | {side + '_account_id': by_code(db,StockAccount,data[side + '_account_code']).id for side in ('source','destination')}
    data = data | dict(related_transfer_id=by_code(db,StockTransfer,data['related_transfer_code']).id if data.get('related_transfer_code') else None,
        fund_transfer_ids=[by_code(db,Transfer,code).id for code in data.get('fund_transfer_codes',[])])
    data = data | dict(lines=[dict(sku_id=warehouse_catalogs.sku_by_code(db, line['sku_code']).id,
                                   quantity=line['quantity']) for line in data['lines']])
    lines = validate(db, data)
    values = {key: data.get(key) for key in ('source_account_id','destination_account_id','description','tags','source_reference','related_transfer_id')}
    values['tags']=data.get('tags',[])
    values['source_reference']=(data.get('source_reference') or '').strip() or None
    item = stock_store.create(db, StockTransfer, values | dict(effective_date=date.fromisoformat(data['effective_date']), actor_id=user.id, status='pending') | source_fields(access))
    for line in lines: stock_store.create(db, StockTransferLine, line | dict(transfer_id=item.id))
    for identifier in data.get('fund_transfer_ids', []): stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=item.id, fund_transfer_id=identifier))
    audit(db, item, user, 'submitted', {}, access=access)
    if apply:
        approve(db, item, user, 'agent_direct' if access else 'automatic', access=access)
        audit(db, item, user, 'automatic_approval', dict(mode=item.approval_mode), access=access)
    return transfer_view(db, item)


def lifecycle(db, user, identifier, data, action, *, access=None):
    authorize_write(db, user)
    require_operator(user, access)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    allowed = ('pending','in_transit') if action == 'cancel' else ('pending',)
    if item.status not in allowed: raise DomainError('货物转移状态不允许该操作', 409)
    if action == 'approve': approve(db, item, user, 'agent_approval' if access else 'manual', access=access)
    else:
        if not data['reason'].strip(): raise DomainError('须填写原因')
        if action == 'cancel':
            for confirmation in stock_store.confirmations(db, item.id):
                if confirmation.status == 'pending': confirmation.status = 'invalidated'
        item.status = 'cancelled' if action == 'cancel' else 'rejected'
        item.reason = data['reason']
    audit(db, item, user, action, dict(status=item.status, reason=item.reason, mode=item.approval_mode), access=access)
    return transfer_view(db, item)


def decide_transfer(db, user, identifier, data, rejection=False, *, access=None):
    return lifecycle(db, user, identifier, data, 'reject' if rejection else 'approve', access=access)
def cancel_transfer(db, user, identifier, data, *, access=None): return lifecycle(db, user, identifier, data, 'cancel', access=access)
def transfer_detail(db, identifier):
    with store.read_snapshot(db) as snapshot:
        timestamp = store.snapshot_timestamp(snapshot)
        return transfer_view(snapshot,get_transfer(snapshot,identifier)) | dict(snapshot_at=timestamp)
def list_transfers(db, status=None, filters=None, page=1, limit=20):
    filters = warehouse_catalogs.sku_filters(db, filters)
    with store.read_snapshot(db) as snapshot:
        timestamp = store.snapshot_timestamp(snapshot)
        items, total = stock_store.transfer_page(
            snapshot, status=status, tag=filters.get('tag'), q=filters.get('q'),
            date_from=filters.get('date_from'), date_to=filters.get('date_to'),
            attention=bool(filters.get('attention')),
            source_account_id=filters.get('source_account_id'),
            destination_account_id=filters.get('destination_account_id'),
            sku_id=filters.get('sku_id'), source_reference=filters.get('source_reference'), page=page, limit=limit)
        return dict(items=[transfer_view(snapshot, item) | dict(snapshot_at=timestamp) for item in items],
                    total=total, page=page, limit=limit, snapshot_at=timestamp)


def confirmation_view(db,item):
    return dict(code=item.code,transfer_code=stock_store.get_transfer(db,item.transfer_id).code) | {key: getattr(item, key) for key in ('actor_id','effective_date','status','approved_by','created_at','submitted_credential_id','submitted_credential_name')}


def post_completion(db, user, item, confirmation, *, access=None, mode=None):
    require_operator(user, access)
    if item.status != 'in_transit' or confirmation.status != 'pending': raise DomainError('确认状态已变化', 409)
    validate(db, business_data(db, item),existing=True)
    source=store.get_stock_account(db,item.source_account_id)
    lines=stock_store.lines(db,item.id)
    if source.kind!='external':
        for line in lines:
            if stock_store.available(db,source.id,line.sku_id)<line.quantity: raise DomainError('来源库存不足',409)
    plan = build_moves(item.source_account_id, item.destination_account_id, [dict(id=line.id, sku_id=line.sku_id, quantity=line.quantity) for line in lines])
    for move in plan:
        stock_store.create(db, StockMove, move | dict(confirmation_id=confirmation.id, effective_date=confirmation.effective_date))
    confirmation.status, confirmation.approved_by = 'completed', user.id
    item.status = 'completed'
    audit(db, item, user, 'completed', dict(confirmation_code=confirmation.code, effective_date=confirmation.effective_date.isoformat(), mode=mode), access=access)


def request_completion(db, user, identifier, data, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    authorize_write(db, user, trusted=False)
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    if item.status != 'in_transit' or any(c.status == 'pending' for c in stock_store.confirmations(db, item.id)):
        raise DomainError('当前不能申请完成', 409)
    confirmation = stock_store.create(db, StockConfirmation, dict(transfer_id=item.id, actor_id=user.id, effective_date=date.fromisoformat(data['effective_date']), status='pending') | source_fields(access))
    audit(db, item, user, 'completion_requested', dict(confirmation_code=confirmation.code, effective_date=data['effective_date']), access=access)
    if apply: post_completion(db, user, item, confirmation, access=access, mode='agent_direct' if access else 'automatic')
    return transfer_view(db, item) | dict(confirmation_code=confirmation.code)


def decide_completion(db, user, identifier, data, rejection=False, *, access=None):
    authorize_write(db, user)
    require_operator(user, access)
    action = 'reject_completion' if rejection else 'approve_completion'
    confirmation = by_code(db, StockConfirmation, identifier)
    if confirmation is None: raise DomainError('完成申请不存在', 404)
    store.refresh(db, confirmation)
    item = stock_store.get_transfer(db, confirmation.transfer_id)
    store.refresh(db, item)
    if confirmation.status != 'pending' or item.status != 'in_transit': raise DomainError('确认状态已变化', 409)
    if rejection:
        if not data['reason'].strip(): raise DomainError('须填写原因')
        confirmation.status = 'rejected'
    else: post_completion(db, user, item, confirmation, access=access, mode='agent_approval' if access else 'manual')
    audit(db, item, user, action, dict(confirmation_code=confirmation.code, status=confirmation.status, reason=data.get('reason')), access=access)
    return transfer_view(db, item)


def inventory(db, filters=None, page=1, limit=20):
    from backend.application.stock_queries import inventory as query_inventory
    return query_inventory(db,filters,page=page,limit=limit)


def list_moves_page(db, filters=None, page=1, limit=20, *, descending=False):
    filters = warehouse_catalogs.sku_filters(db, filters)
    with store.read_snapshot(db) as snapshot:
        timestamp = store.snapshot_timestamp(snapshot)
        moves, total = stock_store.moves_page(snapshot, filters, page=page, limit=limit, descending=descending)
        result = []
        for move in moves:
            confirmation = snapshot.get(StockConfirmation,move.confirmation_id)
            sku = stock_store.get_sku(snapshot,move.sku_id)
            result.append(dict(confirmation_code=confirmation.code,stock_transfer_code=stock_store.get_transfer(snapshot,confirmation.transfer_id).code,
                source_account_code=store.get_stock_account(snapshot,move.source_account_id).code,
                destination_account_code=store.get_stock_account(snapshot,move.destination_account_id).code,
                effective_date=move.effective_date,created_at=move.created_at,sku_code=sku.code,posted_at=move.created_at,
                quantity=quantity_string(move.quantity),sku_name=sku.name,unit=sku.unit,
                source_account_name=store.get_stock_account(snapshot,move.source_account_id).name,
                destination_account_name=store.get_stock_account(snapshot,move.destination_account_id).name,
                applicant_id=confirmation.actor_id,executor_id=confirmation.approved_by,snapshot_at=timestamp))
        return dict(items=result, total=total, page=page, limit=limit, snapshot_at=timestamp)


def business_data(db, item):
    return {key: getattr(item, key) for key in ('source_account_id', 'destination_account_id',   'source_reference', 'related_transfer_id')} | dict(lines=[dict(sku_id=line.sku_id, quantity=quantity_string(line.quantity)) for line in stock_store.lines(db, item.id)], fund_transfer_ids=[reference.fund_transfer_id for reference in stock_store.fund_references(db, item.id)])


def add_fund_reference(db, user, identifier, data, *, access=None):
    authorize_write(db, user)
    require_operator(user, access)
    item = get_transfer(db, identifier)
    fund = by_code(db,Transfer,data['fund_transfer_code'])
    fund_id = fund.id
    if db.get(StockTransferFundReference, (item.id, fund_id)) is None:
        stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=item.id, fund_transfer_id=fund_id))
        audit(db, item, user, 'fund_reference_added', dict(fund_transfer_code=fund.code), access=access)
    return transfer_view(db, item)
