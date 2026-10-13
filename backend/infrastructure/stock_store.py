"""Inventory persistence; writes share the existing transaction and advisory lock."""
from sqlalchemy import select
from backend.infrastructure.models import Base, Sku, LocationProfile, LocationCustody
from backend.infrastructure import store


def get_sku(db, identifier): return db.get(Sku, identifier)
def skus(db): return list(db.scalars(select(Sku).order_by(Sku.name, Sku.id)))
def get_profile(db, identifier): return db.get(LocationProfile, identifier)
def current_custody(db, identifier):
    return db.scalar(select(LocationCustody).where(LocationCustody.location_id == identifier, LocationCustody.valid_to.is_(None)))
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
def location_referenced(db, identifier):
    return referenced(db, 'stock_transfers', ['source_location_id', 'destination_location_id'], identifier)


def initialize_profiles(db):
    store.lock(db)
    identifiers = []
    for location in store.locations(db):
        if get_profile(db, location.id) is None:
            create(db, LocationProfile, dict(location_id=location.id, kind='physical', external_kind=None, active=True))
            identifiers.append(location.id)
    return identifiers

from backend.infrastructure.models import StockTransfer, StockTransferLine, StockTransferFundReference, StockAudit

def get_transfer(db, identifier): return db.get(StockTransfer, identifier)
def transfers(db, status=None):
    query = select(StockTransfer).order_by(StockTransfer.created_at.desc(), StockTransfer.id)
    if status: query = query.where(StockTransfer.status == status)
    return list(db.scalars(query))
def lines(db, identifier):
    return list(db.scalars(select(StockTransferLine).where(StockTransferLine.transfer_id == identifier).order_by(StockTransferLine.id)))
def fund_references(db, identifier):
    return list(db.scalars(select(StockTransferFundReference).where(StockTransferFundReference.stock_transfer_id == identifier).order_by(StockTransferFundReference.fund_transfer_id)))
def existing_submission(db, actor_id, key):
    return db.scalar(select(StockTransfer).where(StockTransfer.actor_id == actor_id, StockTransfer.idempotency_key == key))
def audit_events(db, identifier):
    return list(db.scalars(select(StockAudit).where(StockAudit.stock_transfer_id == identifier).order_by(StockAudit.created_at, StockAudit.id)))
def existing_action(db, actor_id, action, key):
    if not key: return None
    return db.scalar(select(StockAudit).where(StockAudit.actor_id == actor_id, StockAudit.action == action, StockAudit.idempotency_key == key))

from sqlalchemy import func
from backend.infrastructure.models import StockConfirmation, StockMove

def confirmations(db, identifier):
    return list(db.scalars(select(StockConfirmation).where(StockConfirmation.transfer_id == identifier).order_by(StockConfirmation.created_at, StockConfirmation.id)))
def existing_completion(db, actor_id, key):
    return db.scalar(select(StockConfirmation).where(StockConfirmation.actor_id == actor_id, StockConfirmation.idempotency_key == key))
def available(db, location_id, sku_id):
    incoming = db.scalar(select(func.coalesce(func.sum(StockMove.quantity_minor), 0)).where(StockMove.destination_location_id == location_id, StockMove.sku_id == sku_id))
    outgoing = db.scalar(select(func.coalesce(func.sum(StockMove.quantity_minor), 0)).where(StockMove.source_location_id == location_id, StockMove.sku_id == sku_id))
    return incoming - outgoing

def moves(db): return list(db.scalars(select(StockMove).order_by(StockMove.created_at, StockMove.id)))
