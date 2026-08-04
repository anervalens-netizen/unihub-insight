#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "run as root" >&2
  exit 1
}
TARGET="${1:?usage: rollback.sh RELEASE_SHA}"
BASE=/opt/unihub-insight
RELEASE="$BASE/releases/$TARGET"
[[ -d "$RELEASE" ]] || {
  echo "unknown release: $TARGET" >&2
  exit 1
}
ln -sfn "$RELEASE" "$BASE/current.next"
mv -Tf "$BASE/current.next" "$BASE/current"
systemctl restart unihub-insight-api.service
nginx -t
systemctl reload nginx
"$BASE/current/ops/scripts/smoke.sh"
echo "rolled back to $TARGET"
