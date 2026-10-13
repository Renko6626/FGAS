"""Read-only stock queries; physical balances, custody and plans share one SQL snapshot."""
from sqlalchemy import text
from backend.infrastructure import store
from backend.kernel.stock import quantity_string

INVENTORY_SQL = text('''
WITH balances AS (
 SELECT location_id,sku_id,SUM(delta) AS quantity FROM (
  SELECT destination_location_id AS location_id,sku_id,quantity_minor AS delta FROM stock_moves
  UNION ALL SELECT source_location_id,sku_id,-quantity_minor FROM stock_moves
 ) movements GROUP BY location_id,sku_id
), plans AS (
 SELECT location_id,sku_id,SUM(quantity_minor) AS quantity FROM (
 SELECT t.destination_location_id AS location_id,l.sku_id,l.quantity_minor FROM stock_transfers t JOIN stock_transfer_lines l ON l.transfer_id=t.id WHERE t.status='in_transit'
 UNION ALL SELECT t.source_location_id,l.sku_id,l.quantity_minor FROM stock_transfers t JOIN stock_transfer_lines l ON l.transfer_id=t.id WHERE t.status='in_transit'
 ) p GROUP BY location_id,sku_id
)
SELECT statement_timestamp() AS snapshot_at,l.id AS location_id,l.name AS location_name,c.member_id,m.name AS member_name,s.id AS sku_id,s.name AS sku_name,s.unit,COALESCE(b.quantity,0) AS quantity,COALESCE(p.quantity,0) AS in_transit_planned_quantity
FROM stock_locations l JOIN stock_location_profiles profile ON profile.location_id=l.id AND profile.kind='physical'
CROSS JOIN skus s LEFT JOIN location_custodies c ON c.location_id=l.id AND c.valid_to IS NULL LEFT JOIN members m ON m.id=c.member_id
LEFT JOIN balances b ON b.location_id=l.id AND b.sku_id=s.id LEFT JOIN plans p ON p.location_id=l.id AND p.sku_id=s.id
WHERE (CAST(:location_id AS text) IS NULL OR l.id=:location_id) AND (CAST(:sku_id AS text) IS NULL OR s.id=:sku_id) AND (CAST(:member_id AS text) IS NULL OR c.member_id=:member_id)
ORDER BY l.name,l.id,s.name,s.id
''')

def inventory(db,filters=None):
    filters = filters or {}
    rows = list(db.execute(INVENTORY_SQL,{key:filters.get(key) for key in ('location_id','sku_id','member_id')}).mappings())
    quantities,totals = [],{}
    for row in rows:
        value = dict(row)
        value.pop('snapshot_at')
        quantity = int(value['quantity'])
        value['quantity'] = quantity_string(quantity)
        value['in_transit_planned_quantity'] = quantity_string(int(value['in_transit_planned_quantity']))
        value['valuation'] = '未估值'
        quantities.append(value)
        totals[value['sku_id']] = totals.get(value['sku_id'],0)+quantity
    return dict(snapshot_at=rows[0]['snapshot_at'] if rows else db.scalar(text('SELECT statement_timestamp()')),quantities=quantities,totals=[dict(sku_id=sku_id,quantity=quantity_string(quantity),valuation='未估值') for sku_id,quantity in totals.items()])
