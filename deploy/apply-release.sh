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
if $init_db; then
    "${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120 db
    "${compose[@]}" run --rm --no-deps --pull never api python -m backend.application.initialize
fi
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120
"${compose[@]}" ps
echo "Running release: $release_dir"
