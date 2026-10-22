#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AUTH_MODE=development
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://fgas@/fgas_test?host=$PWD/.runtime&port=55438}"
export FGAS_TEST_DATABASE=1
.venv/bin/python - <<'PYDB'
from sqlalchemy import text
from backend.infrastructure.database import engine
with engine.connect() as db:
    name = db.scalar(text('SELECT current_database()'))
    if name != 'fgas_test':
        raise SystemExit('Tests require the dedicated fgas_test database')
    print(f'Test database: {name}')
PYDB
.venv/bin/python -m backend.application.initialize --reset
.venv/bin/python -m pytest backend/tests/test_funds.py backend/tests/test_settlements.py backend/tests/test_stock_transfers.py backend/tests/test_agent_access.py backend/tests/test_auth_casdoor.py backend/tests/test_migrations.py backend/tests/test_dashboard.py -q
