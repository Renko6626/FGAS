#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export AUTH_MODE="${AUTH_MODE:-development}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://fgas@127.0.0.1:55432/fgas}"
.venv/bin/alembic upgrade head
.venv/bin/python -m backend.application.initialize
exec .venv/bin/uvicorn backend.entrypoints.http:app --host 127.0.0.1 --port "${API_PORT:-8000}"
