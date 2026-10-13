"""Thin stocktake persistence and endpoint ownership queries."""
from sqlalchemy import select, or_
from backend.infrastructure.models import FundStocktake, StockStocktake, Transfer, StockTransfer


def model(kind): return FundStocktake if kind == 'fund' else StockStocktake

def get(db, kind, identifier): return db.get(model(kind), identifier)

def stocktakes(db, kind, status=None):
    cls = model(kind)
    query = select(cls).order_by(cls.created_at.desc(), cls.id)
    if status is not None: query = query.where(cls.status == status)
    return list(db.scalars(query))

def create(db, kind, values):
    item = model(kind)(**values)
    db.add(item)
    db.flush()
    return item

def endpoint_owner(db, kind, identifier):
    cls = model(kind)
    endpoint = 'account'
    return db.scalar(select(cls).where(or_(getattr(cls, 'gain_' + endpoint + '_id') == identifier, getattr(cls, 'loss_' + endpoint + '_id') == identifier)))

def transfers(db, kind, item):
    if kind == 'fund':
        direction = or_(Transfer.source_account_id.in_([item.gain_account_id,item.loss_account_id]),Transfer.destination_account_id.in_([item.gain_account_id,item.loss_account_id]))
        originals = select(Transfer.id).where(direction)
        query = select(Transfer).where(or_(direction, Transfer.reversal_of.in_(originals)))
        cls = Transfer
    else:
        cls = StockTransfer
        query = select(cls).where(or_(cls.source_account_id.in_([item.gain_account_id,item.loss_account_id]),cls.destination_account_id.in_([item.gain_account_id,item.loss_account_id])))
    return list(db.scalars(query.order_by(cls.created_at.desc(), cls.id)))


def endpoint_metadata(db, kind, identifier):
    owner = endpoint_owner(db, kind, identifier)
    return {key: getattr(owner, key) for key in ("id", "name", "status")} if owner else None
