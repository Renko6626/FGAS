from backend.infrastructure import store, stock_store, stocktake_store
from backend.infrastructure.models import LocationProfile
from backend.application import warehouse_catalogs
from backend.application.funds import require_trusted, account_view
from backend.kernel.accounting import DomainError

def location_view(db, item): return warehouse_catalogs.location_view(db, item)
def catalog_account_view(db, item):
    return account_view(db, item) | dict(stocktake=stocktake_store.endpoint_metadata(db, "fund", item.id))
def accounts(db, tag=None): return [catalog_account_view(db, item) for item in store.accounts(db, tag)]
def locations(db, tag=None): return [location_view(db, item) for item in store.locations(db, tag)]
def create_account(db, user, values):
    require_trusted(user)
    values = dict(values)
    is_fund = values.pop('is_fund')
    if is_fund and values['kind'] != 'asset': raise DomainError('资金账户须为资产类')
    return catalog_account_view(db, store.create_account(db, values, is_fund))

def update_account(db, user, identifier, values):
    require_trusted(user)
    item = store.get_account(db, identifier)
    if not item: raise DomainError('记账对象不存在', 404)
    store.update(item, values)
    return catalog_account_view(db, item)

def create_location(db, user, values):
    warehouse_catalogs.authorize_write(db, user)
    values = dict(values)
    profile = {key: values.pop(key, default) for key, default in (('kind', 'physical'), ('external_kind', None), ('active', True))}
    warehouse_catalogs.validate_profile(profile['kind'], profile['external_kind'])
    item = store.create_location(db, values)
    stock_store.create(db, LocationProfile, dict(location_id=item.id, **profile))
    return location_view(db, item)

def update_location(db, user, identifier, values):
    warehouse_catalogs.authorize_write(db, user)
    item = store.get_location(db, identifier)
    if not item: raise DomainError('位置不存在', 404)
    values = dict(values)
    profile_values = {key: values.pop(key) for key in ('kind', 'external_kind', 'active') if key in values}
    if any(value is None for key, value in values.items()): raise DomainError('位置字段不能为空')
    if profile_values:
        profile = stock_store.get_profile(db, identifier)
        if profile is None: raise DomainError('旧位置须先显式初始化库存类型', 409)
        kind = profile_values.get('kind', profile.kind)
        external_kind = profile_values.get('external_kind', profile.external_kind)
        warehouse_catalogs.validate_profile(kind, external_kind)
        if profile_values.get('active', profile.active) is None: raise DomainError('启用状态不能为空')
        if (kind, external_kind) != (profile.kind, profile.external_kind):
            if stocktake_store.endpoint_owner(db, 'stock', identifier): raise DomainError('盘点专属端点不能修改库存边界', 409)
            if stock_store.location_referenced(db, identifier): raise DomainError('已有货物转移引用，不能修改库存边界', 409)
            if kind != 'physical' and stock_store.current_custody(db, identifier): raise DomainError('须先结束当前保管关系', 409)
        store.update(profile, profile_values)
    store.update(item, values)
    db.flush()
    return location_view(db, item)
