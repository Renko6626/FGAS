"""Migration baseline checks against a throwaway database."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.infrastructure.models import Base

DATABASE_URL = os.getenv('DATABASE_URL')
BASE_URL = make_url(DATABASE_URL) if DATABASE_URL else None
ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or os.getenv('FGAS_TEST_DATABASE') != '1' or BASE_URL.database != 'fgas_test',
    reason='migration test requires the dedicated fgas_test server',
)


def test_migrations_match_models():
    database = f'fgas_migration_test_{os.getpid()}_{uuid4().hex[:8]}'
    assert database not in ('fgas', 'fgas_test')
    admin_url = BASE_URL.set(database='postgres')
    admin = create_engine(admin_url, isolation_level='AUTOCOMMIT')
    test_url = BASE_URL.set(database=database)
    engine = None
    try:
        with admin.connect() as db:
            db.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
            db.execute(text(f'CREATE DATABASE "{database}"'))

        config = Config(str(ROOT / 'alembic.ini'))
        config.attributes['db_url'] = test_url.render_as_string(hide_password=False)
        command.upgrade(config, 'head')
        command.upgrade(config, 'head')
        command.check(config)

        engine = create_engine(test_url)
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) - {'alembic_version'} == set(Base.metadata.tables)
        transfer_columns = {column['name']: column for column in inspector.get_columns('transfers')}
        assert transfer_columns['posted_at']['type'].timezone is True

        with engine.connect() as db:
            assert db.scalar(text('SELECT version_num FROM alembic_version')) == '0001'
            checks = dict(db.execute(text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype='c' AND connamespace='public'::regnamespace"
            )).all())
            assert len(checks) == 18
            assert checks['ck_transfers_amount_positive']
            assert checks['ck_journal_lines_debit_credit_exclusive']
            uniques = dict(db.execute(text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE contype='u' AND connamespace='public'::regnamespace"
            )).all())
            assert len(uniques) == 9
            assert 'uq_agent_credentials_secret_hash' in uniques
            assert 'uq_skus_code' in uniques
            indexes = {row[0]: row[1] for row in db.execute(text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public'"
            )).all()}
            assert 'WHERE' in indexes['users_sso_subject_key']
            assert 'WHERE' in indexes['one_current_stock_account_custody']
            assert 'WHERE' in indexes['one_pending_stock_confirmation']
            assert 'WHERE' in indexes['one_completed_stock_confirmation']
            assert db.scalar(text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='fund_accounts' AND column_name='tags'"
            )) == 'json'
        engine.dispose()
        engine = None

        command.downgrade(config, 'base')
        with admin.connect() as db:
            remaining = db.scalar(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name <> 'alembic_version'"
            ))
            assert remaining == 0
        command.upgrade(config, 'head')
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as db:
            db.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        admin.dispose()
