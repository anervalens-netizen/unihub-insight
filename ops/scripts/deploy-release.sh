#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "run as root" >&2
  exit 1
}
SOURCE="${1:?usage: deploy-release.sh SOURCE_DIR SOURCE_SHA}"
SOURCE_SHA="${2:?source SHA required}"
BASE=/opt/unihub-insight
RELEASE="$BASE/releases/$SOURCE_SHA"
CURRENT="$BASE/current"
PREVIOUS="$(readlink -f "$CURRENT" 2>/dev/null || true)"

id unihub-insight >/dev/null 2>&1 \
  || useradd --system --home "$BASE" --shell /usr/sbin/nologin unihub-insight
install -d -o unihub-insight -g unihub-insight -m 0750 "$BASE/releases"
[[ ! -e "$RELEASE" ]] || {
  echo "release already exists: $RELEASE" >&2
  exit 1
}
install -d -o unihub-insight -g unihub-insight -m 0750 "$RELEASE"
rsync -a --delete --exclude='.git' "$SOURCE/" "$RELEASE/"
printf '%s\n' "$SOURCE_SHA" > "$RELEASE/SOURCE_SHA"
chown -R unihub-insight:unihub-insight "$RELEASE"

runuser -u unihub-insight -- bash -lc "
  set -euo pipefail
  cd '$RELEASE'
  npm ci --ignore-scripts
  uv sync --project apps/api --frozen --all-groups
  npm run verify
  VITE_API_BASE_URL=/api/v1 \
    VITE_RETAIL_BASE_URL=https://retail.unihub.ro \
    npm run build
  uv sync --project apps/api --frozen --no-dev
"

ln -sfn "$RELEASE" "$BASE/current.next"
mv -Tf "$BASE/current.next" "$CURRENT"
systemctl daemon-reload
if ! systemctl start unihub-insight-migrate.service; then
  [[ -n "$PREVIOUS" ]] && ln -sfn "$PREVIOUS" "$CURRENT"
  exit 1
fi
systemctl restart unihub-insight-api.service
nginx -t
systemctl reload nginx

if ! "$CURRENT/ops/scripts/smoke.sh"; then
  if [[ -n "$PREVIOUS" ]]; then
    ln -sfn "$PREVIOUS" "$CURRENT"
    systemctl restart unihub-insight-api.service
    systemctl reload nginx
  fi
  exit 1
fi

find "$BASE/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr | tail -n +6 | cut -d' ' -f2- | xargs -r rm -rf

echo "deployed $SOURCE_SHA"
