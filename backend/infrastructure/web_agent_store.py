"""Persistence for the single shared webpage-model configuration."""
from backend.infrastructure.models import WebAgentSettings


def get_key(db):
    item = db.get(WebAgentSettings, 1)
    return item.deepseek_api_key if item else None


def save_key(db, key):
    item = db.get(WebAgentSettings, 1)
    if item is None:
        db.add(WebAgentSettings(id=1, deepseek_api_key=key))
    else:
        item.deepseek_api_key = key
    db.flush()


def clear_key(db):
    item = db.get(WebAgentSettings, 1)
    if item is not None:
        db.delete(item)
        db.flush()
