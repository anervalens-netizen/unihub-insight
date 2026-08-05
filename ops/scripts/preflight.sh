#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-/etc/unihub-insight/insight.env}"
MIGRATION_ENV_FILE="${2:-/etc/unihub-insight/migration.env}"
BASE="${UNIHUB_INSIGHT_BASE:-/opt/unihub-insight}"
RELEASE="${3:-$BASE/current}"
LOCAL_API_SOCKET="${UNIHUB_INSIGHT_LOCAL_API_SOCKET:-/run/unihub-insight/api.sock}"

[[ $EUID -eq 0 ]] || {
  echo "run as root so private environment files can be verified" >&2
  exit 1
}

required=(python3 psql curl systemctl docker sha256sum)
for command in "${required[@]}"; do
  command -v "$command" >/dev/null || {
    echo "missing command: $command" >&2
    exit 1
  }
done

[[ -L "$BASE/current" ]] || {
  echo "missing active release symlink: $BASE/current" >&2
  exit 1
}
RELEASE="$(readlink -f "$RELEASE")"
[[ -d "$RELEASE" ]] || {
  echo "missing release: $RELEASE" >&2
  exit 1
}
[[ -s "$RELEASE/apps/web/dist/index.html" ]] || {
  echo "release is missing apps/web/dist/index.html" >&2
  exit 1
}
[[ -x "$RELEASE/apps/api/.venv/bin/python" ]] || {
  echo "release is missing the runtime Python environment" >&2
  exit 1
}

[[ -f "$ENV_FILE" ]] || {
  echo "missing environment file: $ENV_FILE" >&2
  exit 1
}
[[ "$(stat -c '%a' "$ENV_FILE")" == 600 ]] || {
  echo "runtime environment file must use mode 600" >&2
  exit 1
}
[[ -f "$MIGRATION_ENV_FILE" ]] || {
  echo "missing environment file: $MIGRATION_ENV_FILE" >&2
  exit 1
}
[[ "$(stat -c '%a' "$MIGRATION_ENV_FILE")" == 600 ]] || {
  echo "migration environment file must use mode 600" >&2
  exit 1
}
if grep -Eq '^[[:space:]]*UNIHUB_INSIGHT_MIGRATION_DATABASE_URL=' "$ENV_FILE"; then
  echo "migration credential must not be present in the API runtime file" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
# shellcheck disable=SC1090
source "$MIGRATION_ENV_FILE"
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

python3 - "$RELEASE/release-evidence.json" "$RELEASE" "$RELEASE/SOURCE_SHA" <<'PY'
import hashlib
import json
import pathlib
import re
import sys

evidence_path, release, source_sha_path = sys.argv[1:]
evidence = json.loads(pathlib.Path(evidence_path).read_text())
source_sha = pathlib.Path(source_sha_path).read_text().strip()
if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
    raise SystemExit("release source SHA is not exact")
if evidence.get("source_sha") != source_sha:
    raise SystemExit("release evidence source SHA mismatch")
if evidence.get("prepared_host") != "dell-standby":
    raise SystemExit("release was not prepared on dell-standby")
if evidence.get("verified") is not True or evidence.get("build") is not True:
    raise SystemExit("release is not fully verified")
digest = hashlib.sha256()
for path in sorted(pathlib.Path(release, "apps/web/dist").rglob("*")):
    if path.is_file():
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"  ")
        digest.update(str(path.relative_to(release)).encode())
        digest.update(b"\n")
if digest.hexdigest() != evidence.get("dist_sha256"):
    raise SystemExit("release build digest mismatch")
build_info = json.loads(
    pathlib.Path(release, "apps/web/dist/build-info.json").read_text()
)
if build_info != {"source_sha": source_sha}:
    raise SystemExit("public build metadata source SHA mismatch")
PY

systemctl is-active --quiet docker.service
systemctl is-active --quiet unihub-insight-api.service
systemctl is-active --quiet unihub-insight-backup.timer
systemctl is-enabled --quiet unihub-insight-backup.timer
docker inspect unihub_postgres --format '{{.State.Running}}' | grep -qx true
docker exec unihub_postgres pg_isready -q
docker inspect unihub-caddy --format '{{.State.Running}}' | grep -qx true
docker inspect unihub-caddy --format '{{range .Mounts}}{{if eq .Destination "/opt/unihub-insight"}}{{println .Source .Destination .Mode}}{{end}}{{end}}' \
  | grep -Fqx '/opt/unihub-insight /opt/unihub-insight ro'
docker inspect unihub-caddy --format '{{range .Mounts}}{{if eq .Destination "/run/unihub-insight"}}{{println .Source .Destination .Mode}}{{end}}{{end}}' \
  | grep -Fqx '/run/unihub-insight /run/unihub-insight ro'
docker exec unihub-caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile
[[ -S "$LOCAL_API_SOCKET" ]]

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

cd "$RELEASE"
"$RELEASE/apps/api/.venv/bin/python" ops/scripts/migrate.py --check
curl --fail --silent --show-error --max-time 5 --unix-socket "$LOCAL_API_SOCKET" \
  http://localhost/livez \
  | grep -q '"status":"ok"'

echo "preflight complete"
