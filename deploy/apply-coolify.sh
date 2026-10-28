#!/usr/bin/env bash
# Coolify Custom Start Command: bash deploy/apply-coolify.sh
# Requires Preserve Repository; run on the host using Coolify's rendered files.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
export COMPOSE_FILE="$PWD/docker-compose.coolify.yml"
export COMPOSE_PROJECT_NAME="${PWD##*/}"
docker compose config --quiet
docker compose pull
docker compose up -d --no-build --pull never --wait --wait-timeout 120 db

backup_dir=/data/fgas-backups
install -d -m 700 "$backup_dir"
table_count=$(docker compose exec -T db psql -U fgas -d fgas -tAc \
    "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
table_count="${table_count//[[:space:]]/}"
if [[ "$table_count" -gt 0 ]]; then
    backup="$backup_dir/fgas-$(date -u +%Y%m%dT%H%M%SZ)-$$-pre-migrate.dump"
    docker compose exec -T db pg_dump -U fgas -d fgas -Fc --no-owner > "$backup"
    [[ -s "$backup" ]] || { echo 'Database backup is empty; aborting release.' >&2; exit 1; }
    docker compose exec -T db pg_restore --list < "$backup" > /dev/null
    find "$backup_dir" -maxdepth 1 -type f -name 'fgas-*-pre-migrate.dump' -mtime +30 -delete
    echo "Database backup: $backup"
fi

# Explicit run ensures migrations rerun on every release, including redeploys.
docker compose run --rm --no-deps --pull never migrate
docker compose up -d --no-build --pull never --wait --wait-timeout 120
docker compose ps
