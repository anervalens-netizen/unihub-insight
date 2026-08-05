#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-/etc/unihub-insight/insight.env}"

required=(node npm uv python3 psql curl systemctl nginx)
for command in "${required[@]}"; do
  command -v "$command" >/dev/null || {
    echo "missing command: $command" >&2
    exit 1
  }
done

[[ -f "$ENV_FILE" ]] || {
  echo "missing environment file: $ENV_FILE" >&2
  exit 1
}
[[ "$(stat -c '%a' "$ENV_FILE")" =~ ^(600|640)$ ]] || {
  echo "environment file must use mode 600 or 640" >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

for variable in \
  UNIHUB_INSIGHT_DATABASE_URL \
  UNIHUB_INSIGHT_METADATA_DATABASE_URL \
  UNIHUB_INSIGHT_MIGRATION_DATABASE_URL \
  UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET; do
  [[ -n "${!variable:-}" ]] || {
    echo "missing $variable" >&2
    exit 1
  }
done

[[ "${UNIHUB_INSIGHT_ENVIRONMENT:-}" == "production" ]] || {
  echo "UNIHUB_INSIGHT_ENVIRONMENT must be production" >&2
  exit 1
}
[[ "${UNIHUB_INSIGHT_DATA_MODE:-}" == "postgres" ]] || {
  echo "UNIHUB_INSIGHT_DATA_MODE must be postgres" >&2
  exit 1
}
[[ "${UNIHUB_INSIGHT_AUTH_MODE:-}" == "proxy" ]] || {
  echo "UNIHUB_INSIGHT_AUTH_MODE must be proxy" >&2
  exit 1
}
[[ ${#UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET} -ge 32 ]] || {
  echo "trusted proxy secret must have at least 32 characters" >&2
  exit 1
}

psql "$UNIHUB_INSIGHT_DATABASE_URL" -Atqc \
  "SELECT current_setting('transaction_read_only')" | grep -qx on
psql "$UNIHUB_INSIGHT_DATABASE_URL" -Atqc \
  "SELECT has_table_privilege(current_user, 'insight.monthly_review_item_month', 'SELECT')" \
  | grep -qx t
psql "$UNIHUB_INSIGHT_DATABASE_URL" -Atqc \
  "SELECT has_table_privilege(current_user, 'public.sales_transactions', 'SELECT')" \
  | grep -qx f
psql "$UNIHUB_INSIGHT_METADATA_DATABASE_URL" -Atqc \
  "SELECT has_database_privilege(current_user, current_database(), 'CONNECT')" | grep -qx t
psql "$UNIHUB_INSIGHT_METADATA_DATABASE_URL" -Atqc \
  "SELECT has_table_privilege(current_user, 'insight.dashboards', 'SELECT,INSERT,UPDATE,DELETE')" \
  | grep -qx t
psql "$UNIHUB_INSIGHT_METADATA_DATABASE_URL" -Atqc \
  "SELECT has_table_privilege(current_user, 'insight.schema_migrations', 'UPDATE')" \
  | grep -qx f

cd "$ROOT"
npm ci --ignore-scripts
uv sync --project apps/api --frozen --all-groups
npm run verify
uv run --project apps/api python ops/scripts/migrate.py --check
nginx -t

echo "preflight complete"
