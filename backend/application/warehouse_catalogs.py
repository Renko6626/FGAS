import re
from backend.infrastructure import store, stock_store, stocktake_store
from backend.infrastructure.models import Sku, StockAccount, StockAccountCustody, now
from backend.application import directory_views
from backend.application.identity import authorize_write
from backend.kernel.accounting import DomainError


def sku_view(item):
    return directory_views.sku_view(item) | dict(avatar_url=item.avatar_url)
def skus(db, *, code=None, q=None, tag=None, active=None):
    return [sku_view(item) for item in stock_store.skus(db)
            if (code is None or item.code == code.strip().upper())
            and (not q or q.casefold() in item.name.casefold() or q.casefold() in item.code.casefold())
            and (tag is None or tag in item.tags)
            and (active is None or item.active == active)]

def sku_by_code(db, code):
    item = stock_store.get_sku_by_code(db, code)
    if item is None: raise DomainError(f'SKU不存在：{code}', 404)
    return item

def sku_filters(db, filters):
    result = directory_views.code_filters(db, filters, stock=True)
    code = result.pop('sku_code', None)
    if code: result['sku_id'] = sku_by_code(db, code).id
    return result
def validate_sku(values):
    for key in ('name', 'unit'):
        if key in values and (not isinstance(values[key], str) or not values[key].strip()): raise DomainError('名称和单位不能为空')
    if any(value is None for key, value in values.items() if key != 'avatar_url'): raise DomainError('SKU 字段不能为空')
    if 'code' in values:
        code = values['code'].strip().upper()
        if len(code) > 64 or not re.fullmatch(r'[A-Z0-9]+(?:-[A-Z0-9]+)*', code):
            raise DomainError('SKU代号须为字母、数字和连字符，最长64字符')
        values['code'] = code

def validate_unique_code(db, data, current=None):
    if 'code' in data:
        existing = stock_store.get_sku_by_code(db, data['code'])
        if existing is not None and existing is not current:
            raise DomainError(f'SKU代号已存在：{data["code"]}', 409)
def create_sku(db, user, data):
    authorize_write(db, user)
    validate_sku(data)
    validate_unique_code(db, data)
    return sku_view(stock_store.create(db, Sku, data))
def update_sku(db, user, identifier, data):
    authorize_write(db, user)
    item = sku_by_code(db, identifier)
    validate_sku(data)
    validate_unique_code(db, data, item)
    if any(key in data and data[key] != getattr(item, key) for key in ('unit',)) and stock_store.sku_referenced(db, item.id):
        raise DomainError('已有货物转移引用，不能修改单位', 409)
    store.update(item, data)
    db.flush()
    return sku_view(item)


def account_view(db,item):
    return directory_views.account_view(db, item, stock=True) | dict(
        avatar_url=item.avatar_url, stocktake=stocktake_store.endpoint_metadata(db, 'stock', item.id))

def set_responsible(db,user,account_id,member_id):
    authorize_write(db,user)
    item=store.get_stock_account(db,account_id)
    if item is None: raise DomainError('账户不存在',404)
    if member_id is not None and store.get_member(db,member_id) is None: raise DomainError('成员不存在',404)
    current=stock_store.current_custody(db,account_id)
    if (current.member_id if current else None)==member_id: return
    timestamp=now()
    if current:
        current.valid_to=timestamp; current.ended_by=user.id; db.flush()
    if member_id is not None:
        stock_store.create(db,StockAccountCustody,dict(account_id=account_id,member_id=member_id,valid_from=timestamp,actor_id=user.id))


def account_detail(db, identifier):
    with store.read_snapshot(db) as snapshot:
        item = directory_views.by_code(snapshot, StockAccount, identifier)
        if item is None: raise DomainError('账户不存在', 404)
        history = []
        for row in stock_store.responsibility_history(snapshot, item.id):
            history.append(dict(member_code=store.get_member(snapshot, row.member_id).code,
                member_name=store.get_member(snapshot, row.member_id).name,
                valid_from=row.valid_from, valid_to=row.valid_to,
                actor_id=row.actor_id, actor_name=store.get_user(snapshot, row.actor_id).display_name,
                ended_by=row.ended_by,
                ended_by_name=store.get_user(snapshot, row.ended_by).display_name if row.ended_by else None))
        return account_view(snapshot, item) | dict(responsibility_history=history)
