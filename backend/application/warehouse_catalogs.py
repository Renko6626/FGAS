from backend.infrastructure import store, stock_store, stocktake_store
from backend.infrastructure.models import Sku, StockAccountCustody, now
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError


def authorize_write(db, user):
    store.lock(db)
    store.refresh(db, user)
    if not user.active: raise DomainError('用户已停用', 403)
    require_trusted(user)


def sku_view(item):
    return {key: getattr(item, key) for key in ('id', 'name', 'specification', 'unit', 'avatar_url', 'active')}
def skus(db): return [sku_view(item) for item in stock_store.skus(db)]
def validate_sku(values):
    for key in ('name', 'unit'):
        if key in values and (not isinstance(values[key], str) or not values[key].strip()): raise DomainError('名称和单位不能为空')
    if any(value is None for key, value in values.items() if key != 'avatar_url'): raise DomainError('SKU 字段不能为空')
def create_sku(db, user, data):
    authorize_write(db, user)
    validate_sku(data)
    return sku_view(stock_store.create(db, Sku, data))
def update_sku(db, user, identifier, data):
    authorize_write(db, user)
    item = stock_store.get_sku(db, identifier)
    if item is None: raise DomainError('SKU 不存在', 404)
    validate_sku(data)
    if any(key in data and data[key] != getattr(item, key) for key in ('unit',)) and stock_store.sku_referenced(db, identifier):
        raise DomainError('已有货物转移引用，不能修改单位', 409)
    store.update(item, data)
    db.flush()
    return sku_view(item)


def account_view(db,item):
    custody=stock_store.current_custody(db,item.id)
    member=store.get_member(db,custody.member_id) if custody else None
    contact=store.get_member(db,item.member_id) if item.member_id else None
    return {key:getattr(item,key) for key in ('id','name','kind','member_id','avatar_url','tags','active')} | dict(
        member_name=contact.name if contact else None,stocktake=stocktake_store.endpoint_metadata(db,'stock',item.id),
        current_custody=dict(id=custody.id,member_id=member.id,member_name=member.name,valid_from=custody.valid_from,actor_id=custody.actor_id) if custody else None)

def set_custody(db,user,account_id,member_id):
    authorize_write(db,user)
    item=store.get_stock_account(db,account_id)
    if item is None: raise DomainError('账户不存在',404)
    if item.kind=='external': raise DomainError('外部账户不管理社团货物保管关系',409)
    if member_id is not None and store.get_member(db,member_id) is None: raise DomainError('成员不存在',404)
    current=stock_store.current_custody(db,account_id)
    if (current.member_id if current else None)==member_id: return account_view(db,item)
    timestamp=now()
    if current:
        current.valid_to=timestamp; current.ended_by=user.id; db.flush()
    if member_id is not None:
        stock_store.create(db,StockAccountCustody,dict(account_id=account_id,member_id=member_id,valid_from=timestamp,actor_id=user.id))
    return account_view(db,item)
