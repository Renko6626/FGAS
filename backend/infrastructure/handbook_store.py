"""Persistence for the single shared handbook."""
from backend.infrastructure.models import Handbook, now


def get(db):
    return db.get(Handbook, 1)


def save(db, user_id, title, content):
    item = get(db)
    if item is None:
        item = Handbook(id=1)
        db.add(item)
    item.title = title
    item.content = content
    item.updated_by = user_id
    item.updated_at = now()
    db.flush()
    return item
