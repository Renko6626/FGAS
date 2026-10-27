"""Shared directory fields; callers add their protocol-specific projections."""
from backend.infrastructure import store, stock_store
from sqlalchemy import select
from backend.infrastructure.models import FundAccount, StockAccount, Member, Transfer, StockTransfer
from backend.kernel.accounting import DomainError

def by_code(db, model, code):
    item = db.scalar(select(model).where(model.code == code))
    if item is None: raise DomainError(f"业务编号不存在：{code}", 404)
    return item

def code_filters(db, filters, *, stock=False):
    result = dict(filters or {})
    account = StockAccount if stock else FundAccount
    mapping = {"account": account, "source_account": account, "destination_account": account,
               "member": Member, "transfer": StockTransfer if stock else Transfer}
    for key, model in mapping.items():
        code = result.pop(key + "_code", None)
        if code is not None: result[key + "_id"] = by_code(db, model, code).id
    return result


def account_view(db, item, *, stock=False):
    if stock:
        current = stock_store.current_custody(db, item.id)
        member_id = current.member_id if current else None
    else:
        member_id = item.member_id
    member = store.get_member(db, member_id) if member_id else None
    return {key: getattr(item, key) for key in ('code', 'name', 'kind', 'tags', 'active')} | dict(
        member_code=member.code if member else None, member_name=member.name if member else None)


def sku_view(item):
    return {key: getattr(item, key) for key in ('code', 'name', 'tags', 'unit', 'active')}


def member_view(item):
    return dict(code=item.code, name=item.name, note=item.note)
