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


def validate(db, data, transfer_id=None):
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
    if action in ('adjustment_gain', 'adjustment_loss') and transfer_id:
        difference = stock_store.adjustment_difference(db, transfer_id)
        expected_action = 'adjustment_gain' if difference and difference.delta_minor > 0 else 'adjustment_loss'
        valid[action] = bool(difference and action == expected_action and len(data['lines']) == 1 and data['lines'][0]['sku_id'] == difference.sku_id and quantity_to_minor(data['lines'][0]['quantity']) == abs(difference.delta_minor) and ((action == 'adjustment_gain' and direction == ('external','physical') and source.external_kind == action and destination_id == difference.location_id) or (action == 'adjustment_loss' and direction == ('physical','external') and destination.external_kind == action and source_id == difference.location_id)))
    if not valid.get(action, False): raise DomainError('动作与端点方向不符；盘点调整须通过差异入口')
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
    value = {key: getattr(item, key) for key in ('id','source_location_id','destination_location_id','action_kind','effective_date','description','basis','source_reference','actor_id','status','content_version','execution_version','approved_by','approval_mode','approval_snapshot','reason','created_at')}
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
    from backend.application.stock_differences import difference_view
    value['differences'] = [difference_view(db,d) for d in stock_store.differences(db,transfer_id=item.id)]
    linked = stock_store.adjustment_difference(db,item.id)
    value['difference_id'] = linked.id if linked else None
    value['snapshot_at'] = now()
    value['audit'] = [dict(id=a.id, actor_id=a.actor_id, action=a.action, snapshot=a.snapshot, created_at=a.created_at) for a in stock_store.audit_events(db, item.id)]
    return value


def content_snapshot(db, item):
    view = transfer_view(db, item)
    return {key: view[key] for key in ('source_location_id','destination_location_id','source_location_name','destination_location_name','source_kind','destination_kind','source_external_kind','destination_external_kind','action_kind','basis','description','source_reference','lines','fund_references','content_version')} | {'effective_date': item.effective_date.isoformat()}


def audit(db, item, user, action, snapshot, data=None):
    stock_store.create(db, StockAudit, dict(stock_transfer_id=item.id, actor_id=user.id, action=action, snapshot=snapshot, request_payload=data, idempotency_key=data.get('idempotency_key') if data else None))


def approve(db, item, user, mode):
    validate(db, item.payload, item.id)
    item.approval_snapshot = content_snapshot(db, item) | dict(actor_id=user.id, role=user.role, mode=mode, approved_at=now().isoformat())
    item.approved_by, item.approval_mode = user.id, mode
    item.status = 'in_transit'
    item.execution_version += 1


def submit_transfer(db, user, data):
    authorize(db, user)
    existing = stock_store.existing_submission(db, user.id, data['idempotency_key'])
    if existing:
        if existing.payload != data: raise DomainError('幂等键已用于不同内容', 409)
        return transfer_view(db, existing)
    lines = validate(db, data)
    values = {key: data.get(key) for key in ('source_location_id','destination_location_id','action_kind','description','basis','source_reference','idempotency_key')}
    item = stock_store.create(db, StockTransfer, values | dict(effective_date=date.fromisoformat(data['effective_date']), actor_id=user.id, status='pending', payload=data))
    for line in lines: stock_store.create(db, StockTransferLine, line | dict(transfer_id=item.id))
    for identifier in data.get('fund_transfer_ids', []): stock_store.create(db, StockTransferFundReference, dict(stock_transfer_id=item.id, fund_transfer_id=identifier))
    audit(db, item, user, 'submitted', content_snapshot(db, item))
    if user.role in ('admin', 'trusted'):
        approve(db, item, user, 'automatic')
        audit(db, item, user, 'automatic_approval', item.approval_snapshot)
    return transfer_view(db, item)


def lifecycle(db, user, identifier, data, action):
    authorize(db, user, trusted=True)
    request = dict(transfer_id=identifier, **data)
    previous = stock_store.existing_action(db, user.id, action, data.get('idempotency_key'))
    if previous:
        if previous.request_payload != request: raise DomainError('幂等键已用于不同操作内容', 409)
        return transfer_view(db, get_transfer(db, previous.stock_transfer_id))
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    if item.content_version != data['expected_content_version'] or item.execution_version != data['expected_execution_version']:
        raise DomainError('货物转移版本已变化', 409)
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
        item.execution_version += 1
    snapshot = dict(content_version=item.content_version, execution_version=item.execution_version, status=item.status, reason=item.reason, approval=item.approval_snapshot)
    audit(db, item, user, action, snapshot, request)
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
    return {key: getattr(item, key) for key in ('id','transfer_id','content_version','execution_version','actor_id','effective_date','basis','status','approved_by','execution_snapshot','payload','created_at')}


def check_versions(item, data):
    if item.content_version != data['expected_content_version'] or item.execution_version != data['expected_execution_version']:
        raise DomainError('货物转移版本已变化', 409)


def post_completion(db, user, item, confirmation):
    if item.status != 'in_transit' or confirmation.status != 'pending': raise DomainError('确认状态已变化', 409)
    if item.content_version != confirmation.content_version or item.execution_version != confirmation.execution_version:
        raise DomainError('确认绑定版本已变化', 409)
    validate(db,item.payload,item.id)
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
    confirmation.execution_snapshot = content_snapshot(db, item) | dict(confirmation_id=confirmation.id, applicant_id=confirmation.actor_id, executor_id=user.id, role=user.role, effective_date=confirmation.effective_date.isoformat(), basis=confirmation.basis, observations=confirmation.payload.get('observations', []), executed_at=now().isoformat())
    item.status = 'completed'
    item.execution_version += 1
    audit(db, item, user, 'completed', confirmation.execution_snapshot)


def request_completion(db, user, identifier, data):
    authorize(db, user)
    request = dict(transfer_id=identifier, **data)
    previous = stock_store.existing_completion(db, user.id, data['idempotency_key'])
    if previous:
        if previous.payload != request: raise DomainError('幂等键已用于不同内容', 409)
        return transfer_view(db, get_transfer(db, previous.transfer_id))
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    check_versions(item, data)
    if item.status != 'in_transit' or any(c.status == 'pending' for c in stock_store.confirmations(db, item.id)):
        raise DomainError('当前不能申请完成', 409)
    if not data['basis'].strip(): raise DomainError('须填写依据')
    lines = {line.id: line for line in stock_store.lines(db, item.id)}
    seen = set()
    for observation in data.get('observations', []):
        identifier = observation['line_id']
        if identifier not in lines or identifier in seen or not observation['basis'].strip(): raise DomainError('核对明细或依据无效')
        seen.add(identifier)
        # Zero is a valid observation; ordinary stock lines remain positive integers.
        quantity_to_minor(observation['observed_quantity'], allow_zero=True)
    item.execution_version += 1
    confirmation = stock_store.create(db, StockConfirmation, dict(transfer_id=item.id, content_version=item.content_version, execution_version=item.execution_version, actor_id=user.id, effective_date=date.fromisoformat(data['effective_date']), basis=data['basis'], status='pending', payload=request, idempotency_key=data['idempotency_key']))
    audit(db, item, user, 'completion_requested', dict(confirmation_id=confirmation.id, request=request, execution_version=item.execution_version))
    if user.role in ('admin','trusted'): post_completion(db, user, item, confirmation)
    return transfer_view(db, item)


def decide_completion(db, user, identifier, data, rejection=False):
    authorize(db, user, trusted=True)
    action = 'reject_completion' if rejection else 'approve_completion'
    request = dict(confirmation_id=identifier, **data)
    previous = stock_store.existing_action(db, user.id, action, data.get('idempotency_key'))
    if previous:
        if previous.request_payload != request: raise DomainError('幂等键已用于不同内容', 409)
        return transfer_view(db, get_transfer(db, previous.stock_transfer_id))
    confirmation = db.get(StockConfirmation, identifier)
    if confirmation is None: raise DomainError('完成申请不存在', 404)
    store.refresh(db, confirmation)
    item = get_transfer(db, confirmation.transfer_id)
    store.refresh(db, item)
    check_versions(item, data)
    if confirmation.status != 'pending' or item.status != 'in_transit': raise DomainError('确认状态已变化', 409)
    if rejection:
        if not data['reason'].strip(): raise DomainError('须填写原因')
        confirmation.status = 'rejected'
        item.execution_version += 1
    else: post_completion(db, user, item, confirmation)
    audit(db, item, user, action, dict(confirmation_id=confirmation.id, status=confirmation.status, execution_version=item.execution_version, reason=data.get('reason')), request)
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
