#!/usr/bin/env bash
set -euo pipefail

[[ "${1:-}" == "--confirm" ]] || {
  echo "usage: $0 --confirm BACKUP.dump [ENV_FILE]" >&2
  exit 2
}
BACKUP="${2:?backup required}"
ENV_FILE="${3:-/etc/unihub-insight/insight.env}"
[[ -f "$BACKUP" ]] || {
  echo "missing backup: $BACKUP" >&2
  exit 1
}
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
systemctl stop unihub-insight-api.service
pg_restore "$UNIHUB_INSIGHT_MIGRATION_DATABASE_URL" \
  --clean --if-exists --no-owner --schema=insight "$BACKUP"
systemctl start unihub-insight-api.service
"$(dirname "$0")/smoke.sh"
