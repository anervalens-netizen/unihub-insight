#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/etc/unihub-insight/insight.env}"
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
pg_dump "$UNIHUB_INSIGHT_MIGRATION_DATABASE_URL" \
  --format=custom --schema=insight --file="$FILE"
chmod 600 "$FILE"
find "$DESTINATION" -type f -name 'insight_metadata_*.dump' -mtime +30 -delete
printf '%s\n' "$FILE"
