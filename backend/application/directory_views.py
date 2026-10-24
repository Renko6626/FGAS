"""Shared directory fields; callers add their protocol-specific projections."""
from backend.infrastructure import store, stock_store


def account_view(db, item):
    member = store.get_member(db, item.member_id) if item.member_id else None
    return {key: getattr(item, key) for key in ('id', 'name', 'kind', 'member_id', 'tags', 'active')} | dict(
        member_name=member.name if member else None)


def current_custody_view(db, account_id):
    custody = stock_store.current_custody(db, account_id)
    if custody is None:
        return None
    member = store.get_member(db, custody.member_id)
    return dict(id=custody.id, member_id=custody.member_id, member_name=member.name,
                valid_from=custody.valid_from, actor_id=custody.actor_id)


def sku_view(item):
    return {key: getattr(item, key) for key in ('id', 'name', 'specification', 'unit', 'active')}


def member_view(item):
    return dict(id=item.id, name=item.name, note=item.note)
