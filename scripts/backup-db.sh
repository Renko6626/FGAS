#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
command -v pg_dump >/dev/null || { echo 'pg_dump not found; install postgresql-client' >&2; exit 1; }

backup_dir="${FGAS_BACKUP_DIR:-/var/lib/fgas-backup}"
retention_days="${FGAS_BACKUP_RETENTION_DAYS:-30}"
url="${DATABASE_URL/\+psycopg2/}"

mkdir -p "$backup_dir"
file="$backup_dir/fgas-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --file="$file" --dbname="$url"
if [[ ! -s "$file" ]]; then
  echo 'backup file is empty' >&2
  rm -f "$file"
  exit 1
fi
find "$backup_dir" -type f -name 'fgas-*.dump' -mtime +"$retention_days" -delete
echo "backup written: $file"
