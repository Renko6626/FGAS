"""Stock plans and approval; formal quantities are created only by completion."""
from datetime import date
from typing import Literal
from backend.application.agent_access import AgentAccess, auto_apply, require_operator, source_fields, operation_fields
from sqlalchemy import text
from backend.infrastructure import store, stock_store
from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit, now
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError
from backend.kernel.stock import parse_quantity, quantity_string
from backend.modules.warehouse.plans import build_moves
from backend.infrastructure.models import StockConfirmation, StockMove


def authorize(db, user, trusted=False):
    store.lock(db)
    store.refresh(db, user)
    if not user.active: raise DomainError('用户已停用', 403)
    if trusted: require_trusted(user)


def get_transfer(db, identifier):
    item = stock_store.get_transfer(db, identifier)
    if item is None: raise DomainError('货物转移不存在', 404)
    return item


def validate(db,data,existing=False):
    source_id,destination_id=data['source_account_id'],data['destination_account_id']
    if source_id==destination_id: raise DomainError('来源与去向不能相同')
    accounts=[store.get_stock_account(db,i) for i in (source_id,destination_id)]
    if any(a is None for a in accounts): raise DomainError('账户不存在',404)
    if not existing and any(not a.active for a in accounts): raise DomainError('账户已停用',409)
    if all(a.kind=='external' for a in accounts): raise DomainError('不能在两个外部账户间转移')
    if data.get('related_transfer_id'): get_transfer(db,data['related_transfer_id'])
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

def transfer_view(db, item):
    value = {key: getattr(item, key) for key in ('id','source_account_id','destination_account_id','effective_date','description','tags','source_reference','actor_id','status','related_transfer_id','approved_by','approval_mode','approval_snapshot','reason','created_at','submitted_credential_id','submitted_credential_name')}
    for side in ('source', 'destination'):
        account = store.get_stock_account(db, getattr(item, side + '_account_id'))
        value[side + '_account_name'] = account.name
        value[side + '_kind'] = account.kind
    value['lines'] = []
    for line in stock_store.lines(db, item.id):
        sku = stock_store.get_sku(db, line.sku_id)
        value['lines'].append(dict(id=line.id, sku_id=sku.id, sku_name=sku.name, specification=sku.specification, unit=sku.unit, quantity=quantity_string(line.quantity)))
    value['confirmations'] = [confirmation_view(c) for c in stock_store.confirmations(db, item.id)]
    value['fund_references'] = []
    for reference in stock_store.fund_references(db, item.id):
        fund = store.get_transfer(db, reference.fund_transfer_id)
        value['fund_references'].append(dict(id=fund.id,status=fund.status,description=fund.description,amount_minor=fund.amount_minor,reversal_of=fund.reversal_of))
    value['related_transfers']=[dict(id=a.id,status=a.status,source_account_id=a.source_account_id,destination_account_id=a.destination_account_id,
        lines=[dict(sku_id=l.sku_id,quantity=quantity_string(l.quantity)) for l in stock_store.lines(db,a.id)]) for a in stock_store.related_transfers(db,item.id)]
    value['snapshot_at'] = now()
    value['audit'] = [dict(id=a.id, actor_id=a.actor_id, action=a.action, snapshot=a.snapshot, created_at=a.created_at, agent_credential_id=a.agent_credential_id, agent_credential_name=a.agent_credential_name) for a in stock_store.audit_events(db, item.id)]
    return value


def content_snapshot(db, item):
    view = transfer_view(db, item)
    return {key: view[key] for key in ('source_account_id','destination_account_id','source_account_name','destination_account_name','source_kind','destination_kind','description','tags','source_reference','lines','fund_references','related_transfer_id')} | {'effective_date': item.effective_date.isoformat()}


def audit(db, item, user, action, snapshot, *, access=None):
    stock_store.create(db, StockAudit, dict(stock_transfer_id=item.id, actor_id=user.id, action=action, snapshot=snapshot) | operation_fields(access))


def approve(db, item, user, mode, *, access=None):
    require_operator(user, access)
    validate(db, business_data(db, item),existing=True)
    item.approval_snapshot = content_snapshot(db, item) | dict(actor_id=user.id, role=user.role, mode=mode, approved_at=now().isoformat()) | operation_fields(access)
    item.approved_by, item.approval_mode = user.id, mode
    item.status = 'in_transit'


def submit_transfer(db, user, data, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    authorize(db, user)
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    lines = validate(db, data)
    values = {key: data.get(key) for key in ('source_account_id','destination_account_id','description','tags','source_reference','related_transfer_id')}
    values['tags']=data.get('tags',[])
    values['source_reference']=(data.get('source_reference') or '').strip() or None
    item = stock_store.create(db, StockTransfer, values | dict(effective_date=date.fromisoformat(data['effective_date']), actor_id=user.id, status='pending') | source_fields(access))
    for line in lines: stock_store.create(db, StockTransferLine, line | dict(transfer_id=item.id))
    for identifier in data.get('fund_transfer_ids', []): stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=item.id, fund_transfer_id=identifier))
    audit(db, item, user, 'submitted', content_snapshot(db, item), access=access)
    if apply:
        approve(db, item, user, 'agent_direct' if access else 'automatic', access=access)
        audit(db, item, user, 'automatic_approval', item.approval_snapshot, access=access)
    return transfer_view(db, item)


def lifecycle(db, user, identifier, data, action, *, access=None):
    authorize(db, user, trusted=True)
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
    snapshot = dict(status=item.status, reason=item.reason, approval=item.approval_snapshot)
    audit(db, item, user, action, snapshot, access=access)
    return transfer_view(db, item)


def decide_transfer(db, user, identifier, data, rejection=False, *, access=None):
    return lifecycle(db, user, identifier, data, 'reject' if rejection else 'approve', access=access)
def cancel_transfer(db, user, identifier, data, *, access=None): return lifecycle(db, user, identifier, data, 'cancel', access=access)
def transfer_detail(db, identifier):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return transfer_view(snapshot,get_transfer(snapshot,identifier)) | dict(snapshot_at=timestamp)
def list_transfers(db, status=None, filters=None):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return [transfer_view(snapshot,item) | dict(snapshot_at=timestamp) for item in stock_store.transfers(snapshot,status,filters)]


def confirmation_view(item):
    return {key: getattr(item, key) for key in ('id','transfer_id','actor_id','effective_date','status','approved_by','execution_snapshot','created_at','submitted_credential_id','submitted_credential_name')}


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
    confirmation.execution_snapshot = content_snapshot(db, item) | dict(confirmation_id=confirmation.id, applicant_id=confirmation.actor_id, executor_id=user.id, role=user.role, effective_date=confirmation.effective_date.isoformat(), executed_at=now().isoformat(), mode=mode) | operation_fields(access)
    item.status = 'completed'
    audit(db, item, user, 'completed', confirmation.execution_snapshot, access=access)


def request_completion(db, user, identifier, data, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    authorize(db, user)
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    if item.status != 'in_transit' or any(c.status == 'pending' for c in stock_store.confirmations(db, item.id)):
        raise DomainError('当前不能申请完成', 409)
    confirmation = stock_store.create(db, StockConfirmation, dict(transfer_id=item.id, actor_id=user.id, effective_date=date.fromisoformat(data['effective_date']), status='pending') | source_fields(access))
    audit(db, item, user, 'completion_requested', dict(confirmation_id=confirmation.id, effective_date=data['effective_date']), access=access)
    if apply: post_completion(db, user, item, confirmation, access=access, mode='agent_direct' if access else 'automatic')
    return transfer_view(db, item) | dict(confirmation_id=confirmation.id)


def decide_completion(db, user, identifier, data, rejection=False, *, access=None):
    authorize(db, user, trusted=True)
    require_operator(user, access)
    action = 'reject_completion' if rejection else 'approve_completion'
    confirmation = db.get(StockConfirmation, identifier)
    if confirmation is None: raise DomainError('完成申请不存在', 404)
    store.refresh(db, confirmation)
    item = get_transfer(db, confirmation.transfer_id)
    store.refresh(db, item)
    if confirmation.status != 'pending' or item.status != 'in_transit': raise DomainError('确认状态已变化', 409)
    if rejection:
        if not data['reason'].strip(): raise DomainError('须填写原因')
        confirmation.status = 'rejected'
    else: post_completion(db, user, item, confirmation, access=access, mode='agent_approval' if access else 'manual')
    audit(db, item, user, action, dict(confirmation_id=confirmation.id, status=confirmation.status, reason=data.get('reason')), access=access)
    return transfer_view(db, item)


def inventory(db, filters=None):
    from backend.application.stock_queries import inventory as query_inventory
    return query_inventory(db,filters)


def list_moves(db, filters=None):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        result = []
        for move in stock_store.moves(snapshot):
            confirmation = snapshot.get(StockConfirmation,move.confirmation_id)
            if any(value and (confirmation.transfer_id if key == 'transfer_id' else getattr(move,key)) != value for key,value in (filters or {}).items()): continue
            sku = stock_store.get_sku(snapshot,move.sku_id)
            result.append({key: getattr(move, key) for key in ('id','confirmation_id','transfer_line_id','sku_id','source_account_id','destination_account_id','effective_date','created_at')} | dict(quantity=quantity_string(move.quantity),sku_name=sku.name,unit=sku.unit,source_account_name=store.get_stock_account(snapshot,move.source_account_id).name,destination_account_name=store.get_stock_account(snapshot,move.destination_account_id).name,applicant_id=confirmation.actor_id,executor_id=confirmation.approved_by,stock_transfer_id=confirmation.transfer_id,snapshot_at=timestamp))
        return result


def business_data(db, item):
    return {key: getattr(item, key) for key in ('source_account_id', 'destination_account_id',   'source_reference', 'related_transfer_id')} | dict(lines=[dict(sku_id=line.sku_id, quantity=quantity_string(line.quantity)) for line in stock_store.lines(db, item.id)], fund_transfer_ids=[reference.fund_transfer_id for reference in stock_store.fund_references(db, item.id)])


def add_fund_reference(db, user, identifier, data, *, access=None):
    authorize(db, user, trusted=True)
    require_operator(user, access)
    item = get_transfer(db, identifier)
    fund_id = data['fund_transfer_id']
    if store.get_transfer(db, fund_id) is None: raise DomainError('资金引用不存在', 404)
    if db.get(StockTransferFundReference, (identifier, fund_id)) is None:
        stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=identifier, fund_transfer_id=fund_id))
        audit(db, item, user, 'fund_reference_added', dict(fund_transfer_id=fund_id), access=access)
    return transfer_view(db, item)
