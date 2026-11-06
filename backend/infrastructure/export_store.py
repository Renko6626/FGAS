"""Read queries for full ledger exports; callers provide a read snapshot."""
from sqlalchemy import select, text
from backend.infrastructure.models import (
    Transfer, StockTransfer, StockTransferLine, StockMove, StockConfirmation, Sku,
)
from backend.infrastructure.inventory_queries import INVENTORY_BASE


def fund_transfers(db, *, start=None, end=None):
    query = select(Transfer)
    if start is not None:
        query = query.where(Transfer.posted_at > start, Transfer.posted_at <= end)
    return db.scalars(query.order_by(Transfer.created_at, Transfer.id))


def stock_lines(db, *, start=None, end=None):
    query = (select(StockTransfer, StockTransferLine, Sku, StockMove, StockConfirmation)
             .join(StockTransferLine, StockTransferLine.transfer_id == StockTransfer.id)
             .join(Sku, Sku.id == StockTransferLine.sku_id)
             .outerjoin(StockMove, StockMove.transfer_line_id == StockTransferLine.id)
             .outerjoin(StockConfirmation, StockConfirmation.id == StockMove.confirmation_id))
    if start is not None:
        query = query.where(StockMove.created_at > start, StockMove.created_at <= end)
    return db.execute(query.order_by(StockTransfer.created_at, StockTransfer.id, Sku.code))


def inventory(db, as_of):
    # Same zero-inclusive projection as the inventory page, without pagination or plans.
    return db.execute(text(INVENTORY_BASE + '\nSELECT * FROM base ORDER BY account_id, sku_code'),
                      dict(as_of_ts=as_of, as_of_date=None, account_id=None, sku_id=None, member_id=None)).mappings()
