"""Matching records describe settlement; they never create journal lines."""
from sqlalchemy import select
from backend.infrastructure.models import SettlementMatch
from backend.infrastructure import store

def matches(db): return list(db.scalars(select(SettlementMatch)))
def effective(db,match):
    return all(store.get_transfer(db,i).status=='posted' for i in (match.settlement_transfer_id,match.item_transfer_id))
def matched(db,transfer_id,side):
    return sum(m.amount_minor for m in matches(db) if getattr(m,side)==transfer_id and effective(db,m))
def add(db,settlement_id,allocations):
    for item_id,amount in allocations: db.add(SettlementMatch(settlement_transfer_id=settlement_id,item_transfer_id=item_id,amount_minor=amount))
    db.flush()
