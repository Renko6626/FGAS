"""Inventory persistence; writes share the existing transaction and advisory lock."""
from datetime import date, datetime
from sqlalchemy import select
from backend.infrastructure.models import Base, Sku, StockAccountCustody
from backend.infrastructure import store


def get_sku(db, identifier): return db.get(Sku, identifier)
def skus(db): return list(db.scalars(select(Sku).order_by(Sku.name, Sku.id)))
def current_custody(db, identifier):
    return db.scalar(select(StockAccountCustody).where(StockAccountCustody.account_id == identifier, StockAccountCustody.valid_to.is_(None)))
def create(db, model, values):
    item = model(**values)
    db.add(item)
    db.flush()
    return item


def referenced(db, table_name, columns, identifier):
    # The catalogue precedes transfer models; resolve their metadata only when present.
    table = Base.metadata.tables.get(table_name)
    if table is None: return False
    from sqlalchemy import or_
    return db.scalar(select(table.c.id).where(or_(*(table.c[name] == identifier for name in columns))).limit(1)) is not None

def sku_referenced(db, identifier): return referenced(db, 'stock_transfer_lines', ['sku_id'], identifier)
def account_referenced(db, identifier):
    return referenced(db, 'stock_transfers', ['source_account_id', 'destination_account_id'], identifier)


from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit

def get_transfer(db, identifier): return db.get(StockTransfer, identifier)
def transfers(db, status=None, filters=None):
    query = select(StockTransfer).order_by(StockTransfer.created_at.desc(), StockTransfer.id)
    if status: query = query.where(StockTransfer.status == status)
    for name,value in (filters or {}).items():
        if not value: continue
        if name == 'tag': continue
        elif name == 'sku_id': query = query.where(StockTransfer.id.in_(select(StockTransferLine.transfer_id).where(StockTransferLine.sku_id == value)))
        else: query = query.where(getattr(StockTransfer,name) == value)
    return [t for t in db.scalars(query) if not (filters or {}).get('tag') or filters['tag'] in t.tags]
def lines(db, identifier):
    return list(db.scalars(select(StockTransferLine).where(StockTransferLine.transfer_id == identifier).order_by(StockTransferLine.id)))
def fund_references(db, identifier):
    return list(db.scalars(select(StockTransferFundReference).where(StockTransferFundReference.stock_transfer_id == identifier).order_by(StockTransferFundReference.fund_transfer_id)))
def audit_events(db, identifier):
    return list(db.scalars(select(StockAudit).where(StockAudit.stock_transfer_id == identifier).order_by(StockAudit.created_at, StockAudit.id)))
from sqlalchemy import func
from backend.infrastructure.models import StockConfirmation, StockMove

def confirmations(db, identifier):
    return list(db.scalars(select(StockConfirmation).where(StockConfirmation.transfer_id == identifier).order_by(StockConfirmation.created_at, StockConfirmation.id)))
def available(db, account_id, sku_id):
    incoming = db.scalar(select(func.coalesce(func.sum(StockMove.quantity), 0)).where(StockMove.destination_account_id == account_id, StockMove.sku_id == sku_id))
    outgoing = db.scalar(select(func.coalesce(func.sum(StockMove.quantity), 0)).where(StockMove.source_account_id == account_id, StockMove.sku_id == sku_id))
    # PostgreSQL SUM(bigint) returns exact numeric (Decimal); counts are integers.
    return int(incoming) - int(outgoing)

def _as_date(value): return date.fromisoformat(value) if isinstance(value, str) else value
def _as_datetime(value): return datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value

def moves(db, filters=None):
    filters = filters or {}
    query = select(StockMove)
    for name in ('sku_id', 'source_account_id', 'destination_account_id'):
        if filters.get(name) is not None:
            query = query.where(getattr(StockMove, name) == filters[name])
    if filters.get('transfer_id') is not None:
        query = query.where(StockMove.confirmation_id.in_(
            select(StockConfirmation.id).where(StockConfirmation.transfer_id == filters['transfer_id'])))
    if filters.get('effective_date_from') is not None:
        query = query.where(StockMove.effective_date >= _as_date(filters['effective_date_from']))
    if filters.get('effective_date_to') is not None:
        query = query.where(StockMove.effective_date <= _as_date(filters['effective_date_to']))
    for name, column in (('created_at', StockMove.created_at), ('posted_at', StockMove.created_at)):
        if filters.get(name + '_from') is not None:
            query = query.where(column >= _as_datetime(filters[name + '_from']))
        if filters.get(name + '_to') is not None:
            query = query.where(column < _as_datetime(filters[name + '_to']))
    return list(db.scalars(query.order_by(StockMove.created_at, StockMove.id)))

def related_transfers(db, transfer_id):
    return list(db.scalars(select(StockTransfer).where(StockTransfer.related_transfer_id == transfer_id).order_by(StockTransfer.created_at, StockTransfer.id)))
