#!/usr/bin/env bash
set -euo pipefail

TARGET_RELEASE="${1:?usage: check-release-migrations.sh TARGET_RELEASE [ENV_FILE]}"
ENV_FILE="${2:-/etc/unihub-insight/migration.env}"

[[ -d "$TARGET_RELEASE/apps/api/migrations" ]] || {
  echo "target release has no migration catalog: $TARGET_RELEASE" >&2
  exit 1
}
[[ -f "$ENV_FILE" ]] || {
  echo "missing migration environment: $ENV_FILE" >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

applied="$({
  printf '%s\n' "$UNIHUB_INSIGHT_MIGRATION_DATABASE_URL" \
    | docker exec -i unihub_postgres sh -eu -c \
      'IFS= read -r INSIGHT_DSN; export INSIGHT_DSN; exec psql "$INSIGHT_DSN" --no-psqlrc --tuples-only --no-align --command "SET ROLE unihub_insight_schema_owner; SELECT version || '\''|'\'' || checksum FROM insight.schema_migrations ORDER BY version"'
})"

while IFS='|' read -r version expected_checksum; do
  [[ -n "$version" ]] || continue
  migration="$TARGET_RELEASE/apps/api/migrations/$version"
  [[ -f "$migration" ]] || {
    echo "target release is missing applied migration: $version" >&2
    exit 1
  }
  actual_checksum="$(sha256sum "$migration" | cut -d' ' -f1)"
  [[ "$actual_checksum" == "$expected_checksum" ]] || {
    echo "target release migration checksum mismatch: $version" >&2
    exit 1
  }
done <<<"$applied"

echo "target release accepts all applied metadata migrations"
