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


def transfer_page(db, model, filters, credential_id):
    """Filter parent rows before pagination; EXISTS keeps completion matches unique."""
    from datetime import date, datetime
    from sqlalchemy import exists, or_
    from backend.infrastructure.models import StockTransfer, StockTransferLine, StockConfirmation
    statement = select(model)
    for key in ('status', 'source_account_id', 'destination_account_id'):
        if filters.get(key) is not None:
            statement = statement.where(getattr(model, key) == filters[key])
    if filters.get('tag') is not None:
        # JSON tags use the same exact membership semantics as the human queries.
        from sqlalchemy import text
        statement = statement.where(text("EXISTS (SELECT 1 FROM json_array_elements_text(" + model.__tablename__ + ".tags) tag(value) WHERE tag.value = :agent_tag)")).params(agent_tag=filters['tag'])
    for key, column, inclusive in [('effective_date', model.effective_date, True), ('created_at', model.created_at, False)]:
        for endpoint in ('from', 'to'):
            value = filters.get(key + '_' + endpoint)
            if value is None:
                continue
            value = date.fromisoformat(value) if key == 'effective_date' and isinstance(value, str) else datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
            statement = statement.where(column >= value if endpoint == 'from' else column <= value if inclusive else column < value)
    if model is StockTransfer and filters.get('sku_id'):
        statement = statement.where(exists().where(StockTransferLine.transfer_id == model.id, StockTransferLine.sku_id == filters['sku_id']))
    if filters.get('submitted_by_current_connection'):
        source = model.submitted_credential_id == credential_id
        if model is StockTransfer:
            source = or_(source, exists().where(StockConfirmation.transfer_id == model.id, StockConfirmation.submitted_credential_id == credential_id))
        statement = statement.where(source)
    return list(db.scalars(statement.order_by(model.created_at.desc(), model.id.desc()).offset((filters['page'] - 1) * filters['limit']).limit(filters['limit'] + 1)))
