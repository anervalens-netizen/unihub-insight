#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "run as root" >&2
  exit 1
}
BACKUP="${1:?usage: $0 BACKUP.dump [POSTGRES_CONTAINER] [SOURCE_DATABASE]}"
CONTAINER="${2:-unihub_postgres}"
SOURCE_DATABASE="${3:-unihub}"
[[ -f "$BACKUP" ]] || {
  echo "missing backup: $BACKUP" >&2
  exit 1
}
[[ "$CONTAINER" =~ ^[A-Za-z0-9_.-]+$ && "$SOURCE_DATABASE" =~ ^[A-Za-z0-9_]+$ ]] || {
  echo "invalid container or database identifier" >&2
  exit 1
}

RESTORE_DATABASE="unihub_insight_restore_$(date -u +%Y%m%d%H%M%S)_$$"
if docker exec "$CONTAINER" psql -U unihub -d postgres -Atc \
  "SELECT 1 FROM pg_database WHERE datname = '$RESTORE_DATABASE'" | grep -qx 1; then
  echo "refusing existing restore database: $RESTORE_DATABASE" >&2
  exit 1
fi

cleanup_restore() {
  docker exec "$CONTAINER" dropdb -U unihub --if-exists "$RESTORE_DATABASE" >/dev/null
}
trap cleanup_restore EXIT

docker exec "$CONTAINER" createdb -U unihub -T template0 "$RESTORE_DATABASE"
docker exec "$CONTAINER" sh -euc \
  "pg_dump -U unihub -d '$SOURCE_DATABASE' --schema-only --exclude-schema=insight --no-owner --no-privileges \
    | psql -v ON_ERROR_STOP=1 -U unihub -d '$RESTORE_DATABASE' >/dev/null"
docker exec -i "$CONTAINER" pg_restore -U unihub -d "$RESTORE_DATABASE" \
  --no-owner --exit-on-error <"$BACKUP"

SCHEMA_COUNT="$(
  docker exec "$CONTAINER" psql -v ON_ERROR_STOP=1 -U unihub -d "$RESTORE_DATABASE" -Atc \
    "SELECT COUNT(*) FROM pg_namespace WHERE nspname = 'insight'"
)"
MIGRATION_COUNT="$(
  docker exec "$CONTAINER" psql -v ON_ERROR_STOP=1 -U unihub -d "$RESTORE_DATABASE" -Atc \
    "SELECT COUNT(*) FROM insight.schema_migrations"
)"
LATEST_MIGRATION="$(
  docker exec "$CONTAINER" psql -v ON_ERROR_STOP=1 -U unihub -d "$RESTORE_DATABASE" -Atc \
    "SELECT MAX(version) FROM insight.schema_migrations"
)"
[[ "$SCHEMA_COUNT" == "1" && "$MIGRATION_COUNT" =~ ^[1-9][0-9]*$ && -n "$LATEST_MIGRATION" ]] || {
  echo "restored metadata verification failed" >&2
  exit 1
}

printf 'verified backup=%s migrations=%s latest=%s\n' \
  "$(basename "$BACKUP")" "$MIGRATION_COUNT" "$LATEST_MIGRATION"
