from backend.infrastructure import store
from backend.application.funds import require_trusted, account_view
from backend.kernel.accounting import DomainError

def location_view(item): return dict(id=item.id, name=item.name, custodian_label=item.custodian_label, tags=item.tags)
def accounts(db, tag=None): return [account_view(db, item) for item in store.accounts(db, tag)]
def locations(db, tag=None): return [location_view(item) for item in store.locations(db, tag)]
def create_account(db, user, values):
    require_trusted(user)
    values = dict(values)
    is_fund = values.pop('is_fund')
    if is_fund and values['kind'] != 'asset': raise DomainError('资金账户须为资产类')
    return account_view(db, store.create_account(db, values, is_fund))

def update_account(db, user, identifier, values):
    require_trusted(user)
    item = store.get_account(db, identifier)
    if not item: raise DomainError('记账对象不存在', 404)
    store.update(item, values)
    return account_view(db, item)

def create_location(db, user, values):
    require_trusted(user)
    return location_view(store.create_location(db, values))

def update_location(db, user, identifier, values):
    require_trusted(user)
    item = store.get_location(db, identifier)
    if not item: raise DomainError('位置不存在', 404)
    store.update(item, values)
    return location_view(item)
