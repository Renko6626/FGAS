"""Credential persistence; callers own the transaction and never delete credentials."""
from sqlalchemy import select
from backend.infrastructure.models import AgentCredential


def get_by_secret_hash(db, secret_hash):
    return db.scalar(select(AgentCredential).where(AgentCredential.secret_hash == secret_hash))


def get_by_id(db, identifier):
    return db.get(AgentCredential, identifier)


def list_by_owner(db, owner_user_id):
    return list(db.scalars(select(AgentCredential).where(
        AgentCredential.owner_user_id == owner_user_id
    ).order_by(AgentCredential.created_at.desc(), AgentCredential.id)))


def save(db, credential):
    db.add(credential)
    db.flush()
    return credential
