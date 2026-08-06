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
SCHEMA_CURRENT="$BASE/schema-current"
PREVIOUS=""
SCHEMA_PREVIOUS=""
if [[ -L "$CURRENT" ]]; then
  PREVIOUS="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  [[ -n "$PREVIOUS" && -d "$PREVIOUS" && "$PREVIOUS" != "$CURRENT" ]] || {
    echo "active release symlink is invalid: $CURRENT" >&2
    exit 1
  }
elif [[ -e "$CURRENT" ]]; then
  echo "active release path is not a symlink: $CURRENT" >&2
  exit 1
fi
if [[ -L "$SCHEMA_CURRENT" ]]; then
  SCHEMA_PREVIOUS="$(readlink -f "$SCHEMA_CURRENT" 2>/dev/null || true)"
  [[ -n "$SCHEMA_PREVIOUS" && -d "$SCHEMA_PREVIOUS" && "$SCHEMA_PREVIOUS" != "$SCHEMA_CURRENT" ]] || {
    echo "schema release symlink is invalid: $SCHEMA_CURRENT" >&2
    exit 1
  }
elif [[ -e "$SCHEMA_CURRENT" ]]; then
  echo "schema release path is not a symlink: $SCHEMA_CURRENT" >&2
  exit 1
fi

SOURCE="$(cd "$SOURCE" && pwd)"
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "source SHA must be an exact 40-character lowercase Git SHA" >&2
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
build_info = json.loads(pathlib.Path(source, "apps/web/dist/build-info.json").read_text())
if build_info != {"source_sha": expected_sha}:
    raise SystemExit("public build metadata source SHA mismatch")
PY
[[ -s "$SOURCE/apps/web/dist/index.html" ]] || {
  echo "release is missing the verified SPA build" >&2
  exit 1
}

id unihub-insight >/dev/null 2>&1 || {
  echo "missing pre-provisioned service identity: unihub-insight" >&2
  exit 1
}
install -d -o root -g unihub-insight -m 0750 "$BASE/releases"
[[ ! -e "$RELEASE" ]] || {
  echo "release already exists: $RELEASE" >&2
  exit 1
}
install -d -o root -g unihub-insight -m 0750 "$RELEASE"
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
install -d -o root -g unihub-insight -m 0750 "$BASE/python"
install -d -o root -g root -m 0700 "$BASE/cache/uv"
UV_PYTHON_INSTALL_DIR="$BASE/python" \
UV_CACHE_DIR="$BASE/cache/uv" \
UV_LINK_MODE=copy \
  "$UV_BIN" sync --project "$RELEASE/apps/api" --frozen --no-dev
chgrp -R unihub-insight "$BASE/python"
chmod -R g+rX,o-rwx "$BASE/python"
chown -R root:unihub-insight "$RELEASE"

# The service account can read the release but cannot modify it. The root
# deployer retains ownership so old immutable releases can be retired safely.
find "$RELEASE" -type d -exec chmod 0750 {} +
find "$RELEASE" -type f -exec chmod 0640 {} +
find "$RELEASE" -type f \( -path '*/bin/*' -o -name '*.sh' \) -exec chmod 0750 {} +

docker exec unihub-caddy caddy validate \
  --config /etc/caddy/Caddyfile --adapter caddyfile

systemctl daemon-reload
migrate_workdir="$(systemctl show --property=WorkingDirectory --value unihub-insight-migrate.service)"
migrate_exec="$(systemctl show --property=ExecStart --value unihub-insight-migrate.service)"
[[ "$migrate_workdir" == "$SCHEMA_CURRENT" ]] || {
  echo "migration unit must use the forward schema release: $SCHEMA_CURRENT" >&2
  exit 1
}
grep -Fq "$SCHEMA_CURRENT/apps/api/.venv/bin/python" <<<"$migrate_exec"

# Upgrade the legacy single-symlink topology before touching the database.
if [[ -z "$SCHEMA_PREVIOUS" && -n "$PREVIOUS" ]]; then
  ln -sfn "$PREVIOUS" "$BASE/schema-current.next"
  mv -Tf "$BASE/schema-current.next" "$SCHEMA_CURRENT"
  SCHEMA_PREVIOUS="$PREVIOUS"
fi

activate_candidate() {
  ln -sfn "$RELEASE" "$BASE/schema-current.next"
  mv -Tf "$BASE/schema-current.next" "$SCHEMA_CURRENT"
  ln -sfn "$RELEASE" "$BASE/current.next"
  mv -Tf "$BASE/current.next" "$CURRENT"
}

MIGRATION_MAY_HAVE_STARTED=false

restore_previous() {
  if [[ "$MIGRATION_MAY_HAVE_STARTED" == false ]]; then
    if [[ -n "$SCHEMA_PREVIOUS" ]]; then
      ln -sfn "$SCHEMA_PREVIOUS" "$BASE/schema-current.next"
      mv -Tf "$BASE/schema-current.next" "$SCHEMA_CURRENT"
    else
      [[ ! -L "$SCHEMA_CURRENT" ]] || unlink "$SCHEMA_CURRENT"
    fi
  fi
  if [[ -n "$PREVIOUS" ]]; then
    if bash "$CURRENT/ops/scripts/check-release-migrations.sh" "$PREVIOUS"; then
      ln -sfn "$PREVIOUS" "$BASE/current.next"
      mv -Tf "$BASE/current.next" "$CURRENT"
      systemctl reset-failed unihub-insight-migrate.service unihub-insight-api.service || true
      systemctl restart unihub-insight-api.service || true
    else
      echo "previous release is incompatible with applied metadata migrations; keeping candidate active" >&2
      systemctl reset-failed unihub-insight-migrate.service unihub-insight-api.service || true
      systemctl restart unihub-insight-api.service || true
    fi
  else
    [[ ! -L "$CURRENT" ]] || unlink "$CURRENT"
    systemctl stop unihub-insight-api.service >/dev/null 2>&1 || true
  fi
}

# The backup must complete before the forward-only schema pointer advances.
# A first installation needs an active path so its current-based backup unit
# can run; a failed backup restores both pointers before any migration starts.
if [[ -z "$PREVIOUS" ]]; then
  activate_candidate
fi
if ! systemctl start unihub-insight-backup.service; then
  restore_previous
  exit 1
fi
if ! systemctl enable --now unihub-insight-backup.timer; then
  restore_previous
  exit 1
fi
if [[ -n "$PREVIOUS" ]]; then
  activate_candidate
fi
# Restarting the API starts and waits for its required ordered migration unit.
MIGRATION_MAY_HAVE_STARTED=true
if ! systemctl restart unihub-insight-api.service; then
  restore_previous
  exit 1
fi

if ! bash "$CURRENT/ops/scripts/smoke.sh"; then
  restore_previous
  exit 1
fi

while IFS= read -r old_release; do
  [[ "$old_release" == "$BASE/releases/"* ]] || {
    echo "refusing unsafe release cleanup target: $old_release" >&2
    exit 1
  }
  find "$old_release" -depth -delete
done < <(
  find "$BASE/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' \
    | sort -nr | tail -n +6 | cut -d' ' -f2-
)

echo "deployed $SOURCE_SHA"
