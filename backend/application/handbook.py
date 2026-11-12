"""Shared long-lived circle documentation, independent of the ledgers."""
from backend.application.identity import authorize_write
from backend.infrastructure import handbook_store, store
from backend.kernel.accounting import DomainError


def _view(db, item):
    if item is None:
        return dict(title='社团手册', content='', updated_by_id=None, updated_by_name=None, updated_at=None)
    author = store.get_user(db, item.updated_by)
    return dict(title=item.title, content=item.content, updated_by_id=item.updated_by,
                updated_by_name=author.display_name if author else None, updated_at=item.updated_at)


def read(db):
    return _view(db, handbook_store.get(db))


def save(db, user, data):
    authorize_write(db, user)
    title = data['title'].strip()
    if not title:
        raise DomainError('请填写手册标题')
    return _view(db, handbook_store.save(db, user.id, title, data['content']))
