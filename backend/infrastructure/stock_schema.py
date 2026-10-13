"""Explicit, additive compatibility for historical stock schemas."""
from sqlalchemy import inspect, text
from backend.infrastructure.database import engine


def simplify_stock_schema():
    with engine.begin() as db:
        tables = set(inspect(db).get_table_names())
        if 'stock_transfers' not in tables:
            print('No historical stock schema to simplify')
            return
        db.execute(text('ALTER TABLE stock_transfers ADD COLUMN IF NOT EXISTS related_transfer_id VARCHAR REFERENCES stock_transfers(id)'))
        if {'stock_differences', 'stock_difference_adjustments'} <= tables:
            db.execute(text('''UPDATE stock_transfers t SET related_transfer_id=d.stock_transfer_id
                FROM stock_difference_adjustments a JOIN stock_differences d ON d.id=a.difference_id
                WHERE t.id=a.stock_transfer_id AND t.related_transfer_id IS NULL'''))
        for table, columns in {
            'stock_transfers': ('payload', 'idempotency_key', 'content_version', 'execution_version'),
            'stock_confirmations': ('payload', 'idempotency_key', 'content_version', 'execution_version'),
            'stock_audit_events': ('request_payload', 'idempotency_key'),
        }.items():
            if table not in tables: continue
            present = {column['name'] for column in inspect(db).get_columns(table)}
            for column in columns:
                if column in present:
                    db.execute(text(f'ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL'))
        print('Stock schema simplified; historical columns and tables preserved')
