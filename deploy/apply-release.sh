#!/usr/bin/env bash
# Run from ROOT/releases/fgas-VERSION; ROOT/.env survives all releases.
set -euo pipefail
release_dir=$(cd "$(dirname "$0")" && pwd)
deploy_root=$(cd "$release_dir/../.." && pwd)
init_db=false
[[ $# == 0 || ( $# == 1 && $1 == --init-db ) ]] || { echo "Usage: $0 [--init-db]" >&2; exit 2; }
[[ $# == 0 ]] || init_db=true

if [[ ! -f "$deploy_root/.env" ]]; then
    (umask 077; cp "$release_dir/env.example" "$deploy_root/.env")
    echo "Created $deploy_root/.env. Set POSTGRES_PASSWORD (openssl rand -hex 24), then run this script again." >&2
    exit 1
fi
compose=(docker compose --project-name fgas --env-file "$deploy_root/.env"
    --env-file "$release_dir/release.env" -f "$release_dir/compose.yaml")
"${compose[@]}" config --quiet
if [[ -f "$release_dir/images.tar" ]]; then
    docker image load -i "$release_dir/images.tar"
else
    "${compose[@]}" pull
fi

# Start the database first so a backup and migration always see a healthy DB.
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120 db
backup_dir="$deploy_root/backups"
install -d -m 700 "$backup_dir"
table_count=$("${compose[@]}" exec -T db psql -U fgas -d fgas -tAc \
    "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
table_count="${table_count//[[:space:]]/}"
if [[ "$table_count" -gt 0 ]]; then
    backup="$backup_dir/fgas-$(date -u +%Y%m%dT%H%M%SZ)-pre-migrate.dump"
    (umask 077; "${compose[@]}" exec -T db pg_dump -U fgas -d fgas -Fc --no-owner > "$backup")
    [[ -s "$backup" ]] || { echo "Database backup is empty; aborting release." >&2; exit 1; }
    find "$backup_dir" -maxdepth 1 -type f -name 'fgas-*-pre-migrate.dump' -mtime +30 -delete
fi

# Run the one-shot service explicitly: an exited one-shot container is not
# guaranteed to rerun on `up`.
"${compose[@]}" run --rm --no-deps --pull never migrate

if $init_db; then
    "${compose[@]}" run --rm --no-deps --pull never api python -m backend.application.initialize
fi

"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120
"${compose[@]}" ps
echo "Running release: $release_dir"
