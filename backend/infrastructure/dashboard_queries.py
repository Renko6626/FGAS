"""Read-only dashboard projections from formal journals and stock moves."""
from sqlalchemy import text


FUND_CHANGES = '''
WITH changes AS (
 SELECT t.id, t.posted_at, SUM(j.debit_minor-j.credit_minor) AS delta_minor
 FROM journal_lines j JOIN fund_accounts a ON a.id=j.account_id
 JOIN transfers t ON t.id=j.transfer_id
 WHERE a.kind='public'
 GROUP BY t.id
)
'''

STOCK_CHANGES = '''
WITH changes AS (
 SELECT m.*, c.transfer_id,
   ((CASE WHEN d.kind='internal' THEN 1 ELSE 0 END)
    -(CASE WHEN s.kind='internal' THEN 1 ELSE 0 END))*m.quantity AS delta
 FROM stock_moves m
 JOIN stock_accounts s ON s.id=m.source_account_id
 JOIN stock_accounts d ON d.id=m.destination_account_id
 JOIN stock_confirmations c ON c.id=m.confirmation_id
)
'''


def fund_overview(db, window):
    totals = dict(db.execute(text(FUND_CHANGES + '''
 SELECT COALESCE(SUM(delta_minor),0) AS total_minor,
   COALESCE(SUM(delta_minor) FILTER (WHERE delta_minor>0 AND posted_at>=:since AND posted_at<=:until),0) AS incoming_minor,
   COALESCE(SUM(-delta_minor) FILTER (WHERE delta_minor<0 AND posted_at>=:since AND posted_at<=:until),0) AS outgoing_minor
 FROM changes
 '''), window).mappings().one())
    recent = db.execute(text(FUND_CHANGES + '''
 SELECT t.id, t.description, t.reversal_of, c.posted_at, c.delta_minor,
   s.name AS source_account_name, d.name AS destination_account_name
 FROM changes c JOIN transfers t ON t.id=c.id
 JOIN fund_accounts s ON s.id=t.source_account_id
 JOIN fund_accounts d ON d.id=t.destination_account_id
 WHERE c.delta_minor<>0
 ORDER BY c.posted_at DESC NULLS LAST, t.id DESC LIMIT 3
 ''')).mappings()
    return totals, [dict(row) for row in recent]


def stock_overview(db, window):
    rows = db.execute(text(STOCK_CHANGES + '''
 SELECT s.id AS sku_id, s.code AS sku_code, s.name AS sku_name, s.unit, s.avatar_url,
   SUM(c.delta) AS quantity,
   COALESCE(SUM(c.delta) FILTER (WHERE c.delta>0 AND c.created_at>=:since AND c.created_at<=:until),0) AS incoming_quantity,
   COALESCE(SUM(-c.delta) FILTER (WHERE c.delta<0 AND c.created_at>=:since AND c.created_at<=:until),0) AS outgoing_quantity
 FROM changes c JOIN skus s ON s.id=c.sku_id
 GROUP BY s.id
 ORDER BY MAX(c.created_at) FILTER (WHERE c.delta<>0) DESC NULLS LAST, s.name, s.id
 '''), window).mappings()
    recent = db.execute(text(STOCK_CHANGES + '''
 SELECT t.id, t.description, MAX(c.created_at) AS posted_at,
   s.name AS source_account_name, d.name AS destination_account_name,
   jsonb_agg(jsonb_build_object('sku_id',sku.id,'sku_code',sku.code,'sku_name',sku.name,'unit',sku.unit,
     'delta_quantity',c.delta::text) ORDER BY sku.name,sku.id) AS lines
 FROM changes c JOIN stock_transfers t ON t.id=c.transfer_id
 JOIN stock_accounts s ON s.id=t.source_account_id
 JOIN stock_accounts d ON d.id=t.destination_account_id
 JOIN skus sku ON sku.id=c.sku_id
 WHERE c.delta<>0
 GROUP BY t.id,s.name,d.name
 ORDER BY MAX(c.created_at) DESC,t.id DESC LIMIT 3
 ''')).mappings()
    return [dict(row) for row in rows], [dict(row) for row in recent]


def recent_operations(db):
    funds = db.execute(text('''
 SELECT 'funds' AS kind,t.id,t.created_at,t.effective_date,t.description,t.status,
   s.name AS source_account_name,d.name AS destination_account_name,
   u.display_name AS actor_name,t.amount_minor,t.reversal_of
 FROM transfers t JOIN fund_accounts s ON s.id=t.source_account_id
 JOIN fund_accounts d ON d.id=t.destination_account_id
 JOIN users u ON u.id=t.actor_id
 ORDER BY t.created_at DESC,t.id DESC LIMIT 10
 ''')).mappings()
    stock = db.execute(text('''
 SELECT 'stock' AS kind,t.id,t.created_at,t.effective_date,t.description,t.status,
   s.name AS source_account_name,d.name AS destination_account_name,
   u.display_name AS actor_name,
   jsonb_agg(jsonb_build_object('sku_id',sku.id,'sku_code',sku.code,'sku_name',sku.name,
     'unit',sku.unit,'quantity',l.quantity::text) ORDER BY sku.name,sku.id) AS lines
 FROM (SELECT * FROM stock_transfers ORDER BY created_at DESC,id DESC LIMIT 10) t
 JOIN stock_accounts s ON s.id=t.source_account_id
 JOIN stock_accounts d ON d.id=t.destination_account_id
 JOIN users u ON u.id=t.actor_id
 JOIN stock_transfer_lines l ON l.transfer_id=t.id JOIN skus sku ON sku.id=l.sku_id
 GROUP BY t.id,t.created_at,t.effective_date,t.description,t.status,s.name,d.name,u.display_name
 ORDER BY t.created_at DESC,t.id DESC
 ''')).mappings()
    return [dict(row) for row in funds], [dict(row) for row in stock]


def pending_counts(db):
    return dict(db.execute(text('''
 SELECT (SELECT COUNT(*) FROM transfers WHERE status='pending') AS "pendingFunds",
   (SELECT COUNT(*) FROM stock_transfers t WHERE t.status='pending' OR EXISTS (
     SELECT 1 FROM stock_confirmations c WHERE c.transfer_id=t.id AND c.status='pending'
   )) AS "pendingStock",
   (SELECT COUNT(*) FROM stock_transfers WHERE status='in_transit') AS "inTransit"
 ''')).mappings().one())
