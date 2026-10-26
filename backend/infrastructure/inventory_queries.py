"""Read-only inventory projection from formal stock moves and current plans."""
from sqlalchemy import text

INVENTORY_BASE = '''
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
), base AS (
 SELECT statement_timestamp() AS snapshot_at,l.id AS account_id,l.name AS account_name,c.member_id,m.name AS member_name,s.id AS sku_id,s.name AS sku_name,s.unit,COALESCE(b.quantity,0) AS quantity,
 CASE WHEN CAST(:as_of_ts AS timestamptz) IS NULL AND CAST(:as_of_date AS date) IS NULL THEN COALESCE(p.quantity,0) END AS in_transit_planned_quantity
 FROM stock_accounts l
 CROSS JOIN skus s LEFT JOIN stock_account_custodies c ON c.account_id=l.id AND c.valid_to IS NULL LEFT JOIN members m ON m.id=c.member_id
 LEFT JOIN balances b ON b.account_id=l.id AND b.sku_id=s.id LEFT JOIN plans p ON p.account_id=l.id AND p.sku_id=s.id
 WHERE l.kind = 'internal' AND (CAST(:account_id AS text) IS NULL OR l.id=:account_id) AND (CAST(:sku_id AS text) IS NULL OR s.id=:sku_id) AND (CAST(:member_id AS text) IS NULL OR c.member_id=:member_id)
)
'''

INVENTORY_SQL = text(INVENTORY_BASE + '''
SELECT * FROM base ORDER BY account_name,account_id,sku_name,sku_id LIMIT :limit OFFSET :offset
''')
INVENTORY_COUNT_SQL = text(INVENTORY_BASE + '\nSELECT COUNT(*) FROM base\n')
INVENTORY_TOTALS_SQL = text(INVENTORY_BASE + '\nSELECT sku_id,SUM(quantity) AS quantity FROM base GROUP BY sku_id,sku_name ORDER BY sku_name,sku_id\n')


def inventory_page(db, params, *, page=1, limit=20):
    rows = list(db.execute(INVENTORY_SQL, params | dict(limit=limit, offset=(page - 1) * limit)).mappings())
    total = int(db.scalar(INVENTORY_COUNT_SQL, params) or 0)
    totals = list(db.execute(INVENTORY_TOTALS_SQL, params).mappings())
    snapshot_at = rows[0]['snapshot_at'] if rows else db.scalar(text('SELECT statement_timestamp()'))
    return dict(items=rows, total=total, totals=totals, snapshot_at=snapshot_at)
