#!/usr/bin/env bash
set -euo pipefail

TARGET_RELEASE="${1:?usage: check-release-migrations.sh TARGET_RELEASE [ENV_FILE]}"
ENV_FILE="${2:-/etc/unihub-insight/migration.env}"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPATIBILITY_FILE="$SCRIPT_ROOT/rollback-compatible-migrations.txt"

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
      'IFS= read -r INSIGHT_DSN; export INSIGHT_DSN; exec psql "$INSIGHT_DSN" --no-psqlrc --quiet --tuples-only --no-align --command "SET ROLE unihub_insight_schema_owner; SELECT version || '\''|'\'' || checksum FROM insight.schema_migrations ORDER BY version"'
})"

while IFS='|' read -r version expected_checksum; do
  [[ -n "$version" ]] || continue
  migration="$TARGET_RELEASE/apps/api/migrations/$version"
  [[ -f "$migration" ]] || {
    compatible_checksum=""
    if [[ -f "$COMPATIBILITY_FILE" ]]; then
      compatible_checksum="$(awk -F'|' -v version="$version" '$1 == version { print $2; exit }' "$COMPATIBILITY_FILE")"
    fi
    if [[ -n "$compatible_checksum" && "$compatible_checksum" == "$expected_checksum" ]]; then
      echo "target release accepts backward-compatible applied migration: $version"
      continue
    fi
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
