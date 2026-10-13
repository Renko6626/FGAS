"""Stock plans and approval; formal quantities are created only by completion."""
from datetime import date
from sqlalchemy import text
from backend.infrastructure import store, stock_store
from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit, now
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError
from backend.kernel.stock import quantity_to_minor, quantity_string, validate_move
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


def validate(db, data):
    source_id, destination_id = data['source_location_id'], data['destination_location_id']
    if source_id == destination_id: raise DomainError('来源与去向不能相同')
    profiles = [stock_store.get_profile(db, identifier) for identifier in (source_id, destination_id)]
    if any(profile is None or not profile.active for profile in profiles): raise DomainError('位置未配置或已停用', 409)
    source, destination = profiles
    direction = (source.kind, destination.kind)
    if direction == ('external', 'external'): raise DomainError('不能在两个外部位置间转移')
    action = data['action_kind']
    valid = {
        'internal': direction == ('physical', 'physical'),
        'opening': direction == ('external', 'physical') and source.external_kind == 'opening',
        'arrival': direction == ('external', 'physical') and source.external_kind == 'supplier',
        'sale': direction == ('physical', 'external') and destination.external_kind == 'customer',
        'gift': direction == ('physical', 'external') and destination.external_kind == 'customer',
        'loss': direction == ('physical', 'external') and destination.external_kind == 'loss',
        'return': direction == ('physical', 'physical') or (direction == ('physical', 'external') and destination.external_kind == 'supplier') or (direction == ('external', 'physical') and source.external_kind == 'customer'),
    }
    valid['adjustment_gain'] = direction == ('external', 'physical') and source.external_kind == 'adjustment_gain'
    valid['adjustment_loss'] = direction == ('physical', 'external') and destination.external_kind == 'adjustment_loss'
    if not valid.get(action, False): raise DomainError('动作与端点方向不符')
    related = data.get('related_transfer_id')
    if related:
        original = get_transfer(db, related)
        if original.status != 'completed': raise DomainError('关联转移须已完成', 409)
        if action not in ('adjustment_gain', 'adjustment_loss'): raise DomainError('只有盈亏调整可关联原转移')
        physical_id = destination_id if action == 'adjustment_gain' else source_id
        if physical_id not in (original.source_location_id, original.destination_location_id): raise DomainError('调整位置不属于原转移')
        original_skus = {line.sku_id for line in stock_store.lines(db, original.id)}
        if any(line['sku_id'] not in original_skus for line in data['lines']): raise DomainError('调整 SKU 不属于原转移')
    if not data['basis'].strip(): raise DomainError('须填写依据')
    if data.get('source_reference') is not None and not data['source_reference'].strip(): raise DomainError('来源引用不能为空')
    identifiers = [line['sku_id'] for line in data['lines']]
    if not identifiers or len(set(identifiers)) != len(identifiers): raise DomainError('SKU 明细不能为空或重复')
    lines = []
    for line in data['lines']:
        sku = stock_store.get_sku(db, line['sku_id'])
        if sku is None or not sku.active: raise DomainError('SKU 不存在或已停用', 409)
        lines.append(dict(sku_id=sku.id, quantity_minor=quantity_to_minor(line['quantity'])))
    funds = data.get('fund_transfer_ids', [])
    if len(set(funds)) != len(funds): raise DomainError('资金引用不能重复')
    if any(store.get_transfer(db, identifier) is None for identifier in funds): raise DomainError('资金引用不存在', 404)
    return lines


def transfer_view(db, item):
    value = {key: getattr(item, key) for key in ('id','source_location_id','destination_location_id','action_kind','effective_date','description','basis','source_reference','actor_id','status','related_transfer_id','approved_by','approval_mode','approval_snapshot','reason','created_at')}
    for side in ('source', 'destination'):
        location = store.get_location(db, getattr(item, side + '_location_id'))
        profile = stock_store.get_profile(db, location.id)
        value[side + '_location_name'] = location.name
        value[side + '_kind'] = profile.kind
        value[side + '_external_kind'] = profile.external_kind
    value['lines'] = []
    for line in stock_store.lines(db, item.id):
        sku = stock_store.get_sku(db, line.sku_id)
        value['lines'].append(dict(id=line.id, sku_id=sku.id, sku_name=sku.name, specification=sku.specification, unit=sku.unit, quantity_minor=line.quantity_minor, quantity=quantity_string(line.quantity_minor)))
    value['confirmations'] = [confirmation_view(c) for c in stock_store.confirmations(db, item.id)]
    value['fund_references'] = []
    for reference in stock_store.fund_references(db, item.id):
        fund = store.get_transfer(db, reference.fund_transfer_id)
        claim = store.get_claim(db,fund.id)
        business = 'member_claim' if claim else 'repayment' if store.get_repayment(db, fund.id) else 'fund_transfer'
        value['fund_references'].append(dict(id=fund.id, business_type=business, status=fund.status, description=fund.description, amount_minor=fund.amount_minor, member_id=store.get_claim(db,fund.id).member_id if business == 'member_claim' else None, claim_id=fund.id if business == 'member_claim' else None, reversal_of=fund.reversal_of,claim=dict(id=claim.transfer_id,member_id=claim.member_id,declared_minor=claim.declared_minor,confirmed_minor=claim.confirmed_minor,basis=claim.basis) if claim else None))
    value['adjustments'] = [dict(id=a.id, status=a.status, action_kind=a.action_kind, source_location_id=a.source_location_id, destination_location_id=a.destination_location_id, lines=[dict(sku_id=l.sku_id, quantity=quantity_string(l.quantity_minor)) for l in stock_store.lines(db, a.id)]) for a in stock_store.adjustments(db, item.id)]
    value['snapshot_at'] = now()
    value['audit'] = [dict(id=a.id, actor_id=a.actor_id, action=a.action, snapshot=a.snapshot, created_at=a.created_at) for a in stock_store.audit_events(db, item.id)]
    return value


def content_snapshot(db, item):
    view = transfer_view(db, item)
    return {key: view[key] for key in ('source_location_id','destination_location_id','source_location_name','destination_location_name','source_kind','destination_kind','source_external_kind','destination_external_kind','action_kind','basis','description','source_reference','lines','fund_references','related_transfer_id')} | {'effective_date': item.effective_date.isoformat()}


def audit(db, item, user, action, snapshot):
    stock_store.create(db, StockAudit, dict(stock_transfer_id=item.id, actor_id=user.id, action=action, snapshot=snapshot))


def approve(db, item, user, mode):
    validate(db, business_data(db, item))
    item.approval_snapshot = content_snapshot(db, item) | dict(actor_id=user.id, role=user.role, mode=mode, approved_at=now().isoformat())
    item.approved_by, item.approval_mode = user.id, mode
    item.status = 'in_transit'


def submit_transfer(db, user, data):
    authorize(db, user)
    lines = validate(db, data)
    values = {key: data.get(key) for key in ('source_location_id','destination_location_id','action_kind','description','basis','source_reference','related_transfer_id')}
    item = stock_store.create(db, StockTransfer, values | dict(effective_date=date.fromisoformat(data['effective_date']), actor_id=user.id, status='pending'))
    for line in lines: stock_store.create(db, StockTransferLine, line | dict(transfer_id=item.id))
    for identifier in data.get('fund_transfer_ids', []): stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=item.id, fund_transfer_id=identifier))
    audit(db, item, user, 'submitted', content_snapshot(db, item))
    if user.role in ('admin', 'trusted'):
        approve(db, item, user, 'automatic')
        audit(db, item, user, 'automatic_approval', item.approval_snapshot)
    return transfer_view(db, item)


def lifecycle(db, user, identifier, data, action):
    authorize(db, user, trusted=True)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    allowed = ('pending','in_transit') if action == 'cancel' else ('pending',)
    if item.status not in allowed: raise DomainError('货物转移状态不允许该操作', 409)
    if action == 'approve': approve(db, item, user, 'manual')
    else:
        if not data['reason'].strip(): raise DomainError('须填写原因')
        if action == 'cancel':
            for confirmation in stock_store.confirmations(db, item.id):
                if confirmation.status == 'pending': confirmation.status = 'invalidated'
        item.status = 'cancelled' if action == 'cancel' else 'rejected'
        item.reason = data['reason']
    snapshot = dict(status=item.status, reason=item.reason, approval=item.approval_snapshot)
    audit(db, item, user, action, snapshot)
    return transfer_view(db, item)


def decide_transfer(db, user, identifier, data, rejection=False):
    return lifecycle(db, user, identifier, data, 'reject' if rejection else 'approve')
def cancel_transfer(db, user, identifier, data): return lifecycle(db, user, identifier, data, 'cancel')
def transfer_detail(db, identifier):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return transfer_view(snapshot,get_transfer(snapshot,identifier)) | dict(snapshot_at=timestamp)
def list_transfers(db, status=None, filters=None):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return [transfer_view(snapshot,item) | dict(snapshot_at=timestamp) for item in stock_store.transfers(snapshot,status,filters)]


def confirmation_view(item):
    return {key: getattr(item, key) for key in ('id','transfer_id','actor_id','effective_date','basis','status','approved_by','execution_snapshot','created_at')}


def post_completion(db, user, item, confirmation):
    if item.status != 'in_transit' or confirmation.status != 'pending': raise DomainError('确认状态已变化', 409)
    validate(db, business_data(db, item))
    profiles = [stock_store.get_profile(db, identifier) for identifier in (item.source_location_id, item.destination_location_id)]
    for profile in profiles:
        if profile is not None: store.refresh(db, profile)
    if any(profile is None or not profile.active for profile in profiles): raise DomainError('位置未配置或已停用', 409)
    lines = stock_store.lines(db, item.id)
    for line in lines:
        sku = stock_store.get_sku(db, line.sku_id)
        store.refresh(db, sku)
        if not sku.active: raise DomainError('SKU 已停用', 409)
        validate_move(profiles[0].kind, profiles[1].kind, line.quantity_minor, stock_store.available(db, item.source_location_id, line.sku_id) if profiles[0].kind == 'physical' else None)
    plan = build_moves(item.source_location_id, item.destination_location_id, [dict(id=line.id, sku_id=line.sku_id, quantity_minor=line.quantity_minor) for line in lines])
    for move in plan:
        stock_store.create(db, StockMove, move | dict(confirmation_id=confirmation.id, effective_date=confirmation.effective_date))
    confirmation.status, confirmation.approved_by = 'completed', user.id
    confirmation.execution_snapshot = content_snapshot(db, item) | dict(confirmation_id=confirmation.id, applicant_id=confirmation.actor_id, executor_id=user.id, role=user.role, effective_date=confirmation.effective_date.isoformat(), basis=confirmation.basis, executed_at=now().isoformat())
    item.status = 'completed'
    audit(db, item, user, 'completed', confirmation.execution_snapshot)


def request_completion(db, user, identifier, data):
    authorize(db, user)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    if item.status != 'in_transit' or any(c.status == 'pending' for c in stock_store.confirmations(db, item.id)):
        raise DomainError('当前不能申请完成', 409)
    if not data['basis'].strip(): raise DomainError('须填写依据')
    confirmation = stock_store.create(db, StockConfirmation, dict(transfer_id=item.id, actor_id=user.id, effective_date=date.fromisoformat(data['effective_date']), basis=data['basis'], status='pending'))
    audit(db, item, user, 'completion_requested', dict(confirmation_id=confirmation.id, effective_date=data['effective_date'], basis=data['basis']))
    if user.role in ('admin','trusted'): post_completion(db, user, item, confirmation)
    return transfer_view(db, item)


def decide_completion(db, user, identifier, data, rejection=False):
    authorize(db, user, trusted=True)
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
    else: post_completion(db, user, item, confirmation)
    audit(db, item, user, action, dict(confirmation_id=confirmation.id, status=confirmation.status, reason=data.get('reason')))
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
            result.append({key: getattr(move, key) for key in ('id','confirmation_id','transfer_line_id','sku_id','source_location_id','destination_location_id','effective_date','created_at')} | dict(quantity=quantity_string(move.quantity_minor),sku_name=sku.name,unit=sku.unit,source_location_name=store.get_location(snapshot,move.source_location_id).name,destination_location_name=store.get_location(snapshot,move.destination_location_id).name,applicant_id=confirmation.actor_id,executor_id=confirmation.approved_by,stock_transfer_id=confirmation.transfer_id,snapshot_at=timestamp))
        return result


def business_data(db, item):
    return {key: getattr(item, key) for key in ('source_location_id', 'destination_location_id', 'action_kind', 'basis', 'source_reference', 'related_transfer_id')} | dict(lines=[dict(sku_id=line.sku_id, quantity=quantity_string(line.quantity_minor)) for line in stock_store.lines(db, item.id)], fund_transfer_ids=[reference.fund_transfer_id for reference in stock_store.fund_references(db, item.id)])


def add_fund_reference(db, user, identifier, data):
    authorize(db, user, trusted=True)
    item = get_transfer(db, identifier)
    fund_id = data['fund_transfer_id']
    if store.get_transfer(db, fund_id) is None: raise DomainError('资金引用不存在', 404)
    if db.get(StockTransferFundReference, (identifier, fund_id)) is None:
        stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=identifier, fund_transfer_id=fund_id))
        audit(db, item, user, 'fund_reference_added', dict(fund_transfer_id=fund_id))
    return transfer_view(db, item)
