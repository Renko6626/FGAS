"""Shared directory fields; callers add their protocol-specific projections."""
from backend.infrastructure import store, stock_store


def account_view(db, item, *, stock=False):
    if stock:
        current = stock_store.current_custody(db, item.id)
        member_id = current.member_id if current else None
    else:
        member_id = item.member_id
    member = store.get_member(db, member_id) if member_id else None
    return {key: getattr(item, key) for key in ('id', 'name', 'kind', 'tags', 'active')} | dict(
        member_id=member_id, member_name=member.name if member else None)


def sku_view(item):
    return {key: getattr(item, key) for key in ('id', 'code', 'name', 'tags', 'unit', 'active')}


def member_view(item):
    return dict(id=item.id, name=item.name, note=item.note)
