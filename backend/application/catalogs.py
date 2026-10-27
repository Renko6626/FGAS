from backend.infrastructure import store, stocktake_store
from backend.application import directory_views, funds, warehouse_catalogs
from backend.application.identity import authorize_write
from backend.kernel.accounting import DomainError
from backend.application.directory_views import by_code
from backend.infrastructure.models import FundAccount, StockAccount, Member

def normalize_tags(tags): return list(dict.fromkeys(t.strip() for t in tags if t.strip()))
def validate_account(db,values):
    if 'member_code' in values:
        code = values.pop('member_code')
        values['member_id'] = by_code(db, Member, code).id if code is not None else None
    if any(values.get(k) is None for k in ('name','tags','active') if k in values): raise DomainError('名称、标签和启用状态不能为空')
    if 'name' in values and not values['name'].strip(): raise DomainError('账户名称不能为空')
    if values.get('member_id') and not store.get_member(db,values['member_id']): raise DomainError('联系人不存在',404)
    if 'tags' in values: values['tags']=normalize_tags(values['tags'])
    if 'avatar_url' in values: values['avatar_url']=(values['avatar_url'] or '').strip() or None

def catalog_account_view(db,item):
    return directory_views.account_view(db, item) | dict(
        avatar_url=item.avatar_url, balance_minor=funds.balance(db, item),
        stocktake=stocktake_store.endpoint_metadata(db, 'fund', item.id))
def accounts(db,tag=None,kind=None,member_code=None): return [catalog_account_view(db,a) for a in store.accounts(db,tag,kind,by_code(db,Member,member_code).id if member_code else None)]
def stock_accounts(db,tag=None,kind=None,member_code=None): return [warehouse_catalogs.account_view(db,a) for a in store.stock_accounts(db,tag,kind,by_code(db,Member,member_code).id if member_code else None)]
def create_account(db,user,values):
    authorize_write(db,user); validate_account(db,values)
    return catalog_account_view(db,store.create_account(db,values))
def update_account(db,user,identifier,values):
    authorize_write(db,user)
    item=by_code(db,FundAccount,identifier)
    validate_account(db,values); store.update(item,values); store.flush(db)
    return catalog_account_view(db,item)
def create_stock_account(db,user,values):
    authorize_write(db,user); validate_account(db,values)
    values = dict(values)
    member_id = values.pop('member_id', None)
    item = store.create_stock_account(db, values)
    warehouse_catalogs.set_responsible(db, user, item.id, member_id)
    return warehouse_catalogs.account_view(db, item)
def update_stock_account(db,user,identifier,values):
    authorize_write(db,user)
    item=by_code(db,StockAccount,identifier)
    validate_account(db,values)
    values = dict(values)
    if 'member_id' in values:
        warehouse_catalogs.set_responsible(db, user, item.id, values.pop('member_id'))
    store.update(item,values); store.flush(db)
    return warehouse_catalogs.account_view(db,item)
