"""Stock plans and approval; formal quantities are created only by completion."""
import re
from datetime import date
from backend.infrastructure import store, stock_store
from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit, now
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError


def authorize(db, user, trusted=False):
    store.lock(db)
    store.refresh(db, user)
    if not user.active: raise DomainError('用户已停用', 403)
    if trusted: require_trusted(user)


def quantity_to_minor(value, scale):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
        raise DomainError('数量须为正十进制字符串')
    whole, _, fraction = value.partition('.')
    if len(fraction) > scale: raise DomainError('数量超过 SKU 精度')
    # Bound length before converting arbitrary input into a Python integer.
    digits = (whole + fraction.ljust(scale, '0')).lstrip('0')
    if not digits or len(digits) > 16: raise DomainError('数量超出有效范围')
    minor = int(digits)
    if minor > 9007199254740991: raise DomainError('数量超出有效范围')
    return minor


def quantity_string(minor, scale):
    if not scale: return str(minor)
    whole, fraction = divmod(minor, 10 ** scale)
    return f'{whole}.{fraction:0{scale}d}'


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
    if not valid.get(action, False): raise DomainError('动作与端点方向不符；盘点调整须通过差异入口')
    if not data['basis'].strip(): raise DomainError('须填写依据')
    if data.get('source_reference') is not None and not data['source_reference'].strip(): raise DomainError('来源引用不能为空')
    identifiers = [line['sku_id'] for line in data['lines']]
    if not identifiers or len(set(identifiers)) != len(identifiers): raise DomainError('SKU 明细不能为空或重复')
    lines = []
    for line in data['lines']:
        sku = stock_store.get_sku(db, line['sku_id'])
        if sku is None or not sku.active: raise DomainError('SKU 不存在或已停用', 409)
        lines.append(dict(sku_id=sku.id, quantity_minor=quantity_to_minor(line['quantity'], sku.quantity_scale)))
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
        value['lines'].append(dict(id=line.id, sku_id=sku.id, sku_name=sku.name, specification=sku.specification, unit=sku.unit, quantity_scale=sku.quantity_scale, quantity_minor=line.quantity_minor, quantity=quantity_string(line.quantity_minor, sku.quantity_scale)))
    value['fund_references'] = []
    for reference in stock_store.fund_references(db, item.id):
        fund = store.get_transfer(db, reference.fund_transfer_id)
        business = 'member_claim' if store.get_claim(db, fund.id) else 'repayment' if store.get_repayment(db, fund.id) else 'fund_transfer'
        value['fund_references'].append(dict(id=fund.id, business_type=business, status=fund.status, description=fund.description))
    value['audit'] = [dict(id=a.id, actor_id=a.actor_id, action=a.action, snapshot=a.snapshot, created_at=a.created_at) for a in stock_store.audit_events(db, item.id)]
    return value


def content_snapshot(db, item):
    view = transfer_view(db, item)
    return {key: view[key] for key in ('source_location_id','destination_location_id','source_location_name','destination_location_name','source_kind','destination_kind','source_external_kind','destination_external_kind','action_kind','basis','description','source_reference','lines','fund_references','content_version')} | {'effective_date': item.effective_date.isoformat()}


def audit(db, item, user, action, snapshot, data=None):
    stock_store.create(db, StockAudit, dict(stock_transfer_id=item.id, actor_id=user.id, action=action, snapshot=snapshot, request_payload=data, idempotency_key=data.get('idempotency_key') if data else None))


def approve(db, item, user, mode):
    validate(db, item.payload)
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
    with store.read_snapshot(db) as snapshot: return transfer_view(snapshot, get_transfer(snapshot, identifier))
def list_transfers(db, status=None):
    with store.read_snapshot(db) as snapshot: return [transfer_view(snapshot, item) for item in stock_store.transfers(snapshot, status)]
