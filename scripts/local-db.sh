#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PG_BIN=/usr/lib/postgresql/14/bin
FGAS_PG_PORT="${FGAS_PG_PORT:-55432}"
FGAS_PG_SOCKET="${FGAS_PG_SOCKET:-$PWD/.runtime/socket}"
FGAS_PG_HOST="${FGAS_PG_HOST-127.0.0.1}"
mkdir -p "$FGAS_PG_SOCKET"
if [ ! -f .runtime/postgres/PG_VERSION ]; then "$PG_BIN/initdb" -D "$PWD/.runtime/postgres" --username=fgas --auth=trust >/dev/null; fi
if ! "$PG_BIN/pg_ctl" -D "$PWD/.runtime/postgres" status >/dev/null 2>&1; then "$PG_BIN/pg_ctl" -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-p $FGAS_PG_PORT -k $FGAS_PG_SOCKET -h '$FGAS_PG_HOST'" start; fi
FGAS_PG_CONNECT_HOST="${FGAS_PG_HOST:-$FGAS_PG_SOCKET}"
if ! "$PG_BIN/psql" -h "$FGAS_PG_CONNECT_HOST" -p "$FGAS_PG_PORT" -U fgas -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fgas'" | rg -q 1; then "$PG_BIN/createdb" -h "$FGAS_PG_CONNECT_HOST" -p "$FGAS_PG_PORT" -U fgas fgas; fi
