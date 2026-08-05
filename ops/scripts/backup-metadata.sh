#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/etc/unihub-insight/migration.env}"
DESTINATION="${2:-/var/backups/unihub-insight}"
[[ -f "$ENV_FILE" ]] || {
  echo "missing $ENV_FILE" >&2
  exit 1
}
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
mkdir -p "$DESTINATION"
chmod 700 "$DESTINATION"
FILE="$DESTINATION/insight_metadata_$(date -u +%Y%m%dT%H%M%SZ).dump"
printf '%s\n' "$UNIHUB_INSIGHT_MIGRATION_DATABASE_URL" \
  | docker exec -i unihub_postgres sh -eu -c \
    'IFS= read -r INSIGHT_DSN; export INSIGHT_DSN; exec pg_dump "$INSIGHT_DSN" --role=unihub_insight_schema_owner --format=custom --schema=insight' \
    >"$FILE"
chmod 600 "$FILE"
find "$DESTINATION" -type f -name 'insight_metadata_*.dump' -mtime +30 -delete
printf '%s\n' "$FILE"
