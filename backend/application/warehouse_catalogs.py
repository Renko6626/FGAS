from backend.infrastructure import store, stock_store
from backend.infrastructure.models import Sku, LocationProfile, LocationCustody, now
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError


def authorize_write(db, user):
    store.lock(db)
    store.refresh(db, user)
    if not user.active: raise DomainError('用户已停用', 403)
    require_trusted(user)


def sku_view(item):
    return {key: getattr(item, key) for key in ('id', 'name', 'specification', 'unit', 'quantity_scale', 'active')}
def skus(db): return [sku_view(item) for item in stock_store.skus(db)]
def validate_sku(values):
    for key in ('name', 'unit'):
        if key in values and (not isinstance(values[key], str) or not values[key].strip()): raise DomainError('名称和单位不能为空')
    if 'quantity_scale' in values and (type(values['quantity_scale']) is not int or not 0 <= values['quantity_scale'] <= 3): raise DomainError('数量精度须为 0 至 3')
    if any(value is None for value in values.values()): raise DomainError('SKU 字段不能为空')
def create_sku(db, user, data):
    authorize_write(db, user)
    validate_sku(data)
    return sku_view(stock_store.create(db, Sku, data))
def update_sku(db, user, identifier, data):
    authorize_write(db, user)
    item = stock_store.get_sku(db, identifier)
    if item is None: raise DomainError('SKU 不存在', 404)
    validate_sku(data)
    if any(key in data and data[key] != getattr(item, key) for key in ('unit', 'quantity_scale')) and stock_store.sku_referenced(db, identifier):
        raise DomainError('已有货物转移引用，不能修改单位或精度', 409)
    store.update(item, data)
    db.flush()
    return sku_view(item)


def validate_profile(kind, external_kind):
    if kind == 'physical' and external_kind is None: return
    if kind == 'external' and external_kind in ('supplier', 'customer', 'opening', 'loss', 'adjustment_gain', 'adjustment_loss'): return
    raise DomainError('实际位置不能指定外部类型；外部位置须指定有效类型')


def location_view(db, item):
    profile = stock_store.get_profile(db, item.id)
    custody = stock_store.current_custody(db, item.id)
    member = store.get_member(db, custody.member_id) if custody else None
    return dict(id=item.id, name=item.name, custodian_label=item.custodian_label, tags=item.tags,
                kind=profile.kind if profile else None, external_kind=profile.external_kind if profile else None,
                active=profile.active if profile else None,
                current_custody=dict(id=custody.id, member_id=member.id, member_name=member.name,
                                     valid_from=custody.valid_from, actor_id=custody.actor_id) if custody else None)


def set_custody(db, user, location_id, member_id):
    authorize_write(db, user)
    item = store.get_location(db, location_id)
    if item is None: raise DomainError('位置不存在', 404)
    profile = stock_store.get_profile(db, location_id)
    if profile is None or profile.kind != 'physical': raise DomainError('只有已配置的实际位置可以设置保管人', 409)
    if member_id is not None and store.get_member(db, member_id) is None: raise DomainError('成员不存在', 404)
    current = stock_store.current_custody(db, location_id)
    if (current.member_id if current else None) == member_id: return location_view(db, item)
    timestamp = now()
    if current:
        current.valid_to = timestamp
        current.ended_by = user.id
        db.flush()
    if member_id is not None:
        stock_store.create(db, LocationCustody, dict(location_id=location_id, member_id=member_id, valid_from=timestamp, actor_id=user.id))
    return location_view(db, item)
