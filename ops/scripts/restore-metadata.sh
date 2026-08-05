#!/usr/bin/env bash
set -euo pipefail

[[ "${1:-}" == "--confirm" ]] || {
  echo "usage: $0 --confirm BACKUP.dump [ENV_FILE]" >&2
  exit 2
}
BACKUP="${2:?backup required}"
ENV_FILE="${3:-/etc/unihub-insight/migration.env}"
[[ -f "$BACKUP" ]] || {
  echo "missing backup: $BACKUP" >&2
  exit 1
}
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

api_was_active=0
if systemctl is-active --quiet unihub-insight-api.service; then
  api_was_active=1
  systemctl stop unihub-insight-api.service
fi
restart_api_on_exit() {
  local status=$?
  if [[ $api_was_active -eq 1 ]]; then
    systemctl start unihub-insight-api.service || status=1
  fi
  return "$status"
}
trap restart_api_on_exit EXIT

{
  printf '%s\n' "$UNIHUB_INSIGHT_MIGRATION_DATABASE_URL"
  command cat "$BACKUP"
} | docker exec -i unihub_postgres sh -eu -c \
  'IFS= read -r INSIGHT_DSN; export INSIGHT_DSN; exec pg_restore --dbname="$INSIGHT_DSN" --role=unihub_insight_schema_owner --clean --if-exists --no-owner --schema=insight'

if [[ $api_was_active -eq 1 ]]; then
  systemctl start unihub-insight-api.service
fi
trap - EXIT
if [[ $api_was_active -eq 1 ]]; then
  "$(dirname "$0")/smoke.sh"
fi
