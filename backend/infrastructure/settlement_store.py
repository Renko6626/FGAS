"""Persistence for settlement matches and their transfer endpoints."""
from sqlalchemy import or_, select
from backend.infrastructure.models import SettlementMatch, Transfer


def matches_with_endpoints(db, transfer_ids=None):
    query = select(SettlementMatch)
    if transfer_ids is not None:
        query = query.where(or_(SettlementMatch.settlement_transfer_id.in_(transfer_ids),
                                SettlementMatch.item_transfer_id.in_(transfer_ids)))
    matches = list(db.scalars(query))
    endpoint_ids = set(transfer_ids or ())
    for match in matches:
        endpoint_ids.update((match.settlement_transfer_id, match.item_transfer_id))
    endpoints = {item.id: item for item in db.scalars(select(Transfer).where(Transfer.id.in_(endpoint_ids)))}
    return matches, endpoints


def add(db,settlement_id,allocations):
    for item_id,amount in allocations: db.add(SettlementMatch(settlement_transfer_id=settlement_id,item_transfer_id=item_id,amount_minor=amount))
    db.flush()
