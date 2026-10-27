"""Inventory persistence; writes share the existing transaction and advisory lock."""
from datetime import date, datetime
from sqlalchemy import select, or_, cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased
from backend.infrastructure.models import Base, Sku, StockAccountCustody


def get_sku(db, identifier): return db.get(Sku, identifier)
def get_sku_by_code(db, code): return db.scalar(select(Sku).where(Sku.code == code.strip().upper()))
def skus(db): return list(db.scalars(select(Sku).order_by(Sku.name, Sku.id)))
def current_custody(db, identifier):
    return db.scalar(select(StockAccountCustody).where(StockAccountCustody.account_id == identifier, StockAccountCustody.valid_to.is_(None)))
def responsibility_history(db, identifier):
    return list(db.scalars(select(StockAccountCustody).where(StockAccountCustody.account_id == identifier)
                           .order_by(StockAccountCustody.valid_from, StockAccountCustody.id)))
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


from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit, StockAccount, StockConfirmation, StockMove

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
def transfer_page(db, *, status=None, tag=None, q=None, date_from=None, date_to=None, attention=False,
                  source_account_id=None, destination_account_id=None, sku_id=None, source_reference=None, page=1, limit=20):
    source, destination = aliased(StockAccount), aliased(StockAccount)
    query = (select(StockTransfer)
             .join(source, StockTransfer.source_account_id == source.id)
             .join(destination, StockTransfer.destination_account_id == destination.id))
    if status: query = query.where(StockTransfer.status == status)
    if attention:
        pending = select(StockConfirmation.transfer_id).where(StockConfirmation.status == 'pending')
        query = query.where(or_(StockTransfer.status == 'pending', StockTransfer.id.in_(pending)))
    if tag: query = query.where(cast(StockTransfer.tags, JSONB).contains([tag]))
    if date_from: query = query.where(StockTransfer.effective_date >= date_from)
    if date_to: query = query.where(StockTransfer.effective_date <= date_to)
    if source_account_id: query = query.where(StockTransfer.source_account_id == source_account_id)
    if destination_account_id: query = query.where(StockTransfer.destination_account_id == destination_account_id)
    if sku_id: query = query.where(StockTransfer.id.in_(select(StockTransferLine.transfer_id).where(StockTransferLine.sku_id == sku_id)))
    if source_reference is not None: query = query.where(StockTransfer.source_reference == source_reference)
    if q:
        pattern = f'%{q}%'
        sku_matches = (select(StockTransferLine.transfer_id)
                       .join(Sku, Sku.id == StockTransferLine.sku_id)
                       .where(or_(Sku.name.ilike(pattern), Sku.code.ilike(pattern))))
        query = query.where(or_(source.name.ilike(pattern), destination.name.ilike(pattern),
                                StockTransfer.description.ilike(pattern), StockTransfer.code.ilike(pattern), StockTransfer.source_reference.ilike(pattern), source.code.ilike(pattern), destination.code.ilike(pattern),
                                StockTransfer.id.in_(sku_matches)))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = list(db.scalars(query.order_by(StockTransfer.created_at.desc(), StockTransfer.id.desc())
                            .offset((page - 1) * limit).limit(limit)))
    return items, total
def lines(db, identifier):
    return list(db.scalars(select(StockTransferLine).where(StockTransferLine.transfer_id == identifier).order_by(StockTransferLine.id)))
def fund_references(db, identifier):
    return list(db.scalars(select(StockTransferFundReference).where(StockTransferFundReference.stock_transfer_id == identifier).order_by(StockTransferFundReference.fund_transfer_id)))
def audit_events(db, identifier):
    return list(db.scalars(select(StockAudit).where(StockAudit.stock_transfer_id == identifier).order_by(StockAudit.created_at, StockAudit.id)))
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
    return list(db.scalars(_moves_query(filters or {}).order_by(StockMove.created_at, StockMove.id)))
def moves_page(db, filters=None, page=1, limit=20, *, descending=False):
    query = _moves_query(filters or {})
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    order = (StockMove.created_at.desc(), StockMove.id.desc()) if descending else (StockMove.created_at, StockMove.id)
    items = list(db.scalars(query.order_by(*order)
                            .offset((page - 1) * limit).limit(limit)))
    return items, total
def _moves_query(filters):
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
    return query

def related_transfers(db, transfer_id):
    return list(db.scalars(select(StockTransfer).where(StockTransfer.related_transfer_id == transfer_id).order_by(StockTransfer.created_at, StockTransfer.id)))
