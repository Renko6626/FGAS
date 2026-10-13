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
