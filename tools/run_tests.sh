#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AUTH_MODE=development
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://fgas@/fgas_test?host=$PWD/.runtime&port=55438}"
export FGAS_TEST_DATABASE=1
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m pytest backend/tests/test_funds.py -q
