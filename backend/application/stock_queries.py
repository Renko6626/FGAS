"""Read-only stock queries; physical balances, custody and plans share one SQL snapshot."""
from sqlalchemy import text
from backend.infrastructure import store
from backend.kernel.stock import quantity_string

INVENTORY_SQL = text('''
WITH moves AS (
 SELECT * FROM stock_moves
 WHERE (CAST(:as_of_ts AS timestamptz) IS NULL OR created_at <= CAST(:as_of_ts AS timestamptz))
   AND (CAST(:as_of_date AS date) IS NULL OR effective_date <= CAST(:as_of_date AS date))
), balances AS (
 SELECT account_id,sku_id,SUM(delta) AS quantity FROM (
  SELECT destination_account_id AS account_id,sku_id,quantity AS delta FROM moves
  UNION ALL SELECT source_account_id,sku_id,-quantity FROM moves
 ) movements GROUP BY account_id,sku_id
), plans AS (
 SELECT account_id,sku_id,SUM(quantity) AS quantity FROM (
 SELECT t.destination_account_id AS account_id,l.sku_id,l.quantity FROM stock_transfers t JOIN stock_transfer_lines l ON l.transfer_id=t.id WHERE t.status='in_transit'
 AND CAST(:as_of_ts AS timestamptz) IS NULL AND CAST(:as_of_date AS date) IS NULL
 UNION ALL SELECT t.source_account_id,l.sku_id,l.quantity FROM stock_transfers t JOIN stock_transfer_lines l ON l.transfer_id=t.id WHERE t.status='in_transit'
 AND CAST(:as_of_ts AS timestamptz) IS NULL AND CAST(:as_of_date AS date) IS NULL
 ) p GROUP BY account_id,sku_id
)
SELECT statement_timestamp() AS snapshot_at,l.id AS account_id,l.name AS account_name,c.member_id,m.name AS member_name,s.id AS sku_id,s.name AS sku_name,s.unit,COALESCE(b.quantity,0) AS quantity,
 CASE WHEN CAST(:as_of_ts AS timestamptz) IS NULL AND CAST(:as_of_date AS date) IS NULL THEN COALESCE(p.quantity,0) END AS in_transit_planned_quantity
FROM stock_accounts l
CROSS JOIN skus s LEFT JOIN stock_account_custodies c ON c.account_id=l.id AND c.valid_to IS NULL LEFT JOIN members m ON m.id=c.member_id
LEFT JOIN balances b ON b.account_id=l.id AND b.sku_id=s.id LEFT JOIN plans p ON p.account_id=l.id AND p.sku_id=s.id
WHERE l.kind IN ('public','private') AND (CAST(:account_id AS text) IS NULL OR l.id=:account_id) AND (CAST(:sku_id AS text) IS NULL OR s.id=:sku_id) AND (CAST(:member_id AS text) IS NULL OR l.member_id=:member_id) AND (CAST(:custodian_id AS text) IS NULL OR c.member_id=:custodian_id)
ORDER BY l.name,l.id,s.name,s.id
''')

def inventory(db,filters=None):
    filters = filters or {}
    as_of = filters.get('as_of')
    basis = filters.get('basis', 'posted')
    as_of_ts = as_of if as_of is not None and basis == 'posted' else None
    as_of_date = as_of.date() if as_of is not None and basis == 'effective_date' else None
    params = {key:filters.get(key) for key in ('account_id','sku_id','member_id','custodian_id')}
    params.update(as_of_ts=as_of_ts, as_of_date=as_of_date)
    rows = list(db.execute(INVENTORY_SQL,params).mappings())
    quantities,totals = [],{}
    for row in rows:
        value = dict(row)
        value.pop('snapshot_at')
        quantity = int(value['quantity'])
        value['quantity'] = quantity_string(quantity)
        if value['in_transit_planned_quantity'] is not None:
            value['in_transit_planned_quantity'] = quantity_string(int(value['in_transit_planned_quantity']))
        value['valuation'] = '未估值'
        quantities.append(value)
        totals[value['sku_id']] = totals.get(value['sku_id'],0)+quantity
    return dict(snapshot_at=rows[0]['snapshot_at'] if rows else db.scalar(text('SELECT statement_timestamp()')),quantities=quantities,totals=[dict(sku_id=sku_id,quantity=quantity_string(quantity),valuation='未估值') for sku_id,quantity in totals.items()],as_of=as_of,basis=basis if as_of is not None else None)
