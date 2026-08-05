#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "run as root" >&2
  exit 1
}
TARGET="${1:?usage: rollback.sh RELEASE_SHA}"
BASE="${UNIHUB_INSIGHT_BASE:-/opt/unihub-insight}"
RELEASE="$BASE/releases/$TARGET"
PREVIOUS="$(readlink -f "$BASE/current" 2>/dev/null || true)"
[[ -d "$RELEASE" ]] || {
  echo "unknown release: $TARGET" >&2
  exit 1
}
[[ -s "$RELEASE/apps/web/dist/index.html" && -x "$RELEASE/apps/api/.venv/bin/python" ]] || {
  echo "release is not deployable: $TARGET" >&2
  exit 1
}
bash "$BASE/current/ops/scripts/check-release-migrations.sh" "$RELEASE"
docker exec unihub-caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile
ln -sfn "$RELEASE" "$BASE/current.next"
mv -Tf "$BASE/current.next" "$BASE/current"
restore_previous() {
  if [[ -n "$PREVIOUS" && "$PREVIOUS" != "$RELEASE" ]]; then
    ln -sfn "$PREVIOUS" "$BASE/current.next"
    mv -Tf "$BASE/current.next" "$BASE/current"
    systemctl restart unihub-insight-api.service || true
  fi
}
if ! systemctl restart unihub-insight-api.service; then
  restore_previous
  exit 1
fi
if ! bash "$BASE/current/ops/scripts/smoke.sh"; then
  restore_previous
  exit 1
fi
echo "rolled back to $TARGET"
