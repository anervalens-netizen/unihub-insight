#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || {
  echo "run as root" >&2
  exit 1
}
SOURCE="${1:?usage: deploy-release.sh SOURCE_DIR SOURCE_SHA}"
SOURCE_SHA="${2:?source SHA required}"
BASE="${UNIHUB_INSIGHT_BASE:-/opt/unihub-insight}"
RELEASE="$BASE/releases/$SOURCE_SHA"
CURRENT="$BASE/current"
PREVIOUS="$(readlink -f "$CURRENT" 2>/dev/null || true)"

SOURCE="$(cd "$SOURCE" && pwd)"
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{7,64}$ ]] || {
  echo "source SHA must be a lowercase hexadecimal Git SHA" >&2
  exit 1
}
[[ -f "$SOURCE/release-evidence.json" ]] || {
  echo "release is not prepared by prepare-release.sh" >&2
  exit 1
}
python3 - "$SOURCE/release-evidence.json" "$SOURCE_SHA" "$SOURCE" <<'PY'
import hashlib
import json
import pathlib
import sys

evidence_path, expected_sha, source = sys.argv[1:]
evidence = json.loads(pathlib.Path(evidence_path).read_text())
if evidence.get("source_sha") != expected_sha:
    raise SystemExit("release evidence source SHA mismatch")
if evidence.get("prepared_host") != "dell-standby":
    raise SystemExit("release must be prepared on dell-standby")
if evidence.get("verified") is not True or evidence.get("build") is not True:
    raise SystemExit("release evidence is not fully verified")
digest = hashlib.sha256()
for path in sorted(pathlib.Path(source, "apps/web/dist").rglob("*")):
    if path.is_file():
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"  ")
        digest.update(str(path.relative_to(source)).encode())
        digest.update(b"\n")
if digest.hexdigest() != evidence.get("dist_sha256"):
    raise SystemExit("release build digest mismatch")
PY
[[ -s "$SOURCE/apps/web/dist/index.html" ]] || {
  echo "release is missing the verified SPA build" >&2
  exit 1
}

id unihub-insight >/dev/null 2>&1 \
  || useradd --system --home "$BASE" --shell /usr/sbin/nologin unihub-insight
install -d -o unihub-insight -g unihub-insight -m 0750 "$BASE/releases"
[[ ! -e "$RELEASE" ]] || {
  echo "release already exists: $RELEASE" >&2
  exit 1
}
install -d -o unihub-insight -g unihub-insight -m 0750 "$RELEASE"
rsync -a --delete --exclude='.git/' --exclude='node_modules/' --exclude='.venv/' "$SOURCE/" "$RELEASE/"
printf '%s\n' "$SOURCE_SHA" > "$RELEASE/SOURCE_SHA"
chown -R root:unihub-insight "$RELEASE"

UV_BIN="${UNIHUB_INSIGHT_UV:-$BASE/bin/uv}"
if [[ ! -x "$UV_BIN" ]]; then
  UV_BIN="$(command -v uv || true)"
fi
[[ -x "$UV_BIN" ]] || {
  echo "missing runtime uv; install it at $BASE/bin/uv or set UNIHUB_INSIGHT_UV" >&2
  exit 1
}
"$UV_BIN" sync --project "$RELEASE/apps/api" --frozen --no-dev

# The service account can read the release but cannot modify it. The root
# deployer retains ownership so old immutable releases can be retired safely.
find "$RELEASE" -type d -exec chmod 0750 {} +
find "$RELEASE" -type f -exec chmod 0640 {} +
find "$RELEASE" -type f \( -path '*/bin/*' -o -name '*.sh' \) -exec chmod 0750 {} +

ln -sfn "$RELEASE" "$BASE/current.next"
mv -Tf "$BASE/current.next" "$CURRENT"
systemctl daemon-reload

restore_previous() {
  if [[ -n "$PREVIOUS" ]]; then
    ln -sfn "$PREVIOUS" "$BASE/current.next"
    mv -Tf "$BASE/current.next" "$CURRENT"
    systemctl restart unihub-insight-api.service || true
  fi
}

if ! systemctl start unihub-insight-migrate.service; then
  restore_previous
  exit 1
fi
if ! systemctl restart unihub-insight-api.service; then
  restore_previous
  exit 1
fi
if ! docker exec unihub-caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile; then
  restore_previous
  exit 1
fi

if ! bash "$CURRENT/ops/scripts/smoke.sh"; then
  restore_previous
  exit 1
fi

find "$BASE/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
  | sort -nr | tail -n +6 | cut -d' ' -f2- | xargs -r rm -rf

echo "deployed $SOURCE_SHA"
