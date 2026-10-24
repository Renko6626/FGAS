from backend.infrastructure import store, stocktake_store
from backend.application import directory_views, funds, warehouse_catalogs
from backend.application.identity import authorize_write
from backend.kernel.accounting import DomainError

def normalize_tags(tags): return list(dict.fromkeys(t.strip() for t in tags if t.strip()))
def validate_account(db,values):
    if any(values.get(k) is None for k in ('name','tags','active') if k in values): raise DomainError('名称、标签和启用状态不能为空')
    if 'name' in values and not values['name'].strip(): raise DomainError('账户名称不能为空')
    if values.get('member_id') and not store.get_member(db,values['member_id']): raise DomainError('联系人不存在',404)
    if 'tags' in values: values['tags']=normalize_tags(values['tags'])
    if 'avatar_url' in values: values['avatar_url']=(values['avatar_url'] or '').strip() or None

def catalog_account_view(db,item):
    return directory_views.account_view(db, item) | dict(
        avatar_url=item.avatar_url, balance_minor=funds.balance(db, item),
        stocktake=stocktake_store.endpoint_metadata(db, 'fund', item.id))
def accounts(db,tag=None,kind=None,member_id=None): return [catalog_account_view(db,a) for a in store.accounts(db,tag,kind,member_id)]
def stock_accounts(db,tag=None,kind=None,member_id=None): return [warehouse_catalogs.account_view(db,a) for a in store.stock_accounts(db,tag,kind,member_id)]
def create_account(db,user,values):
    authorize_write(db,user); validate_account(db,values)
    return catalog_account_view(db,store.create_account(db,values))
def update_account(db,user,identifier,values):
    authorize_write(db,user)
    item=store.get_account(db,identifier)
    if not item: raise DomainError('账户不存在',404)
    validate_account(db,values); store.update(item,values); store.flush(db)
    return catalog_account_view(db,item)
def create_stock_account(db,user,values):
    authorize_write(db,user); validate_account(db,values)
    return warehouse_catalogs.account_view(db,store.create_stock_account(db,values))
def update_stock_account(db,user,identifier,values):
    authorize_write(db,user)
    item=store.get_stock_account(db,identifier)
    if not item: raise DomainError('账户不存在',404)
    validate_account(db,values); store.update(item,values); store.flush(db)
    return warehouse_catalogs.account_view(db,item)
