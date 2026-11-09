#!/usr/bin/env bash
# Coolify Custom Start Command: bash deploy/apply-coolify.sh
# Requires Preserve Repository; run on the host using Coolify's rendered files.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
# Newer Coolify versions render routing/container metadata into this file.
# The repository's docker-compose.coolify.yml can still be the unrendered template.
if [[ -f "$PWD/docker-compose.yaml" ]]; then
    export COMPOSE_FILE="$PWD/docker-compose.yaml"
else
    export COMPOSE_FILE="$PWD/docker-compose.coolify.yml"
fi
export COMPOSE_PROJECT_NAME="${PWD##*/}"
docker compose config --quiet
docker compose pull
docker compose up -d --no-build --pull never --wait --wait-timeout 120 db

backup_dir=/data/fgas-backups
install -d -m 700 "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
table_count=$(docker compose exec -T db psql -U fgas -d fgas -tAc \
    "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
table_count="${table_count//[[:space:]]/}"
if [[ "$table_count" -gt 0 ]]; then
    backup="$backup_dir/fgas-$stamp-$$-pre-migrate.dump"
    docker compose exec -T db pg_dump -U fgas -d fgas -Fc --no-owner > "$backup"
    [[ -s "$backup" ]] || { echo 'Database backup is empty; aborting release.' >&2; exit 1; }
    docker compose exec -T db pg_restore --list < "$backup" > /dev/null
    find "$backup_dir" -maxdepth 1 -type f -name 'fgas-*-pre-migrate.dump' -mtime +30 -delete
    echo "Database backup: $backup"
fi

attachments="$backup_dir/fgas-$stamp-$$-attachments.tar"
if docker compose run --rm --no-deps --pull never -T api test -d /data/attachments; then
    docker compose run --rm --no-deps --pull never -T api tar -C /data -cf - attachments > "$attachments"
    [[ -s "$attachments" ]] || { echo 'Attachment backup is empty; aborting release.' >&2; exit 1; }
    find "$backup_dir" -maxdepth 1 -type f -name 'fgas-*-attachments.tar' -mtime +30 -delete
    echo "Attachment backup: $attachments"
fi

# Explicit run ensures migrations rerun on every release, including redeploys.
docker compose run --rm --no-deps --pull never migrate
docker compose up -d --no-build --pull never --wait --wait-timeout 120
docker compose ps
