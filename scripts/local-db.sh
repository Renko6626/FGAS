#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/socket
PG_BIN=/usr/lib/postgresql/14/bin
if [ ! -f .runtime/postgres/PG_VERSION ]; then "$PG_BIN/initdb" -D "$PWD/.runtime/postgres" --username=fgas --auth=trust >/dev/null; fi
if ! "$PG_BIN/pg_ctl" -D "$PWD/.runtime/postgres" status >/dev/null 2>&1; then "$PG_BIN/pg_ctl" -D "$PWD/.runtime/postgres" -l "$PWD/.runtime/postgres.log" -o "-p 55432 -k $PWD/.runtime/socket -h 127.0.0.1" start; fi
if ! "$PG_BIN/psql" -h 127.0.0.1 -p 55432 -U fgas -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fgas'" | rg -q 1; then "$PG_BIN/createdb" -h 127.0.0.1 -p 55432 -U fgas fgas; fi
