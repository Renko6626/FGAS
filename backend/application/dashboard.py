"""Homepage: public funds, organization-owned stock, and recent operations."""
from datetime import datetime, timedelta, timezone

from backend.infrastructure import dashboard_queries


def overview(db):
    snapshot_at = datetime.now(timezone.utc)
    since = snapshot_at - timedelta(days=7)
    window = dict(since=since, until=snapshot_at)
    totals, fund_recent = dashboard_queries.fund_overview(db, window)
    funds = {key: int(value) for key, value in totals.items()}
    funds['net_minor'] = funds['incoming_minor'] - funds['outgoing_minor']
    funds['recent'] = [row | dict(delta_minor=int(row['delta_minor'])) for row in fund_recent]

    stock_rows, stock_recent = dashboard_queries.stock_overview(db, window)
    skus = []
    for row in stock_rows:
        quantity, incoming, outgoing = (int(row[key]) for key in ('quantity', 'incoming_quantity', 'outgoing_quantity'))
        # Keep depleted items visible when they changed during this week.
        if quantity == 0 and incoming == 0 and outgoing == 0:
            continue
        skus.append(row | dict(quantity=str(quantity), incoming_quantity=str(incoming),
                               outgoing_quantity=str(outgoing), net_quantity=str(incoming-outgoing)))

    fund_operations, stock_operations = dashboard_queries.recent_operations(db)
    operations = sorted(fund_operations + stock_operations,
                        key=lambda row: (row['created_at'], row['kind'], row['id']), reverse=True)[:10]
    return dict(snapshot_at=snapshot_at, window_start=since,
                funds=funds, stock=dict(skus=skus, recent=stock_recent),
                counts=dashboard_queries.pending_counts(db),
                operations=dict(all=operations, funds=fund_operations, stock=stock_operations))
