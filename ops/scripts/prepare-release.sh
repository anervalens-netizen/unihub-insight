#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:?usage: prepare-release.sh SOURCE_DIR SOURCE_SHA OUTPUT_DIR}"
SOURCE_SHA="${2:?source SHA required}"
OUTPUT="${3:?output directory required}"

[[ -d "$SOURCE" ]] || {
	echo "missing source directory: $SOURCE" >&2
	exit 1
}
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{7,64}$ ]] || {
	echo "source SHA must be a lowercase hexadecimal Git SHA" >&2
	exit 1
}
SOURCE="$(cd "$SOURCE" && pwd)"
OUTPUT="$(mkdir -p "$(dirname "$OUTPUT")" && cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")"
case "$OUTPUT/" in
"$SOURCE/"*)
	echo "output directory must be outside the source directory" >&2
	exit 1
;;
esac
[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$SOURCE_SHA" ]] || {
	echo "source HEAD does not match $SOURCE_SHA" >&2
	exit 1
}
[[ -z "$(git -C "$SOURCE" status --porcelain)" ]] || {
	echo "source checkout must be clean" >&2
	exit 1
}
[[ ! -e "$OUTPUT" ]] || {
	echo "output already exists: $OUTPUT" >&2
	exit 1
}

for command in git node npm rsync sha256sum sort xargs awk; do
	command -v "$command" >/dev/null || {
		echo "missing command: $command" >&2
		exit 1
	}
done

UV_BIN="${UNIHUB_INSIGHT_UV:-}"
if [[ -z "$UV_BIN" ]]; then
	UV_BIN="$(command -v uv || true)"
fi
[[ -x "$UV_BIN" ]] || {
	echo "missing executable uv; set UNIHUB_INSIGHT_UV if needed" >&2
	exit 1
}

install -d -m 0750 "$OUTPUT"
rsync -a --delete \
	--exclude='.git/' \
	--exclude='node_modules/' \
	--exclude='.venv/' \
	--exclude='apps/web/dist/' \
	"$SOURCE/" "$OUTPUT/"

cd "$OUTPUT"
npm ci --ignore-scripts
"$UV_BIN" sync --project apps/api --frozen --all-groups
VITE_API_BASE_URL=/api/v1 \
VITE_RETAIL_BASE_URL=https://retail.unihub.ro \
npm run verify
[[ -s apps/web/dist/index.html ]] || {
	echo "verified build did not produce apps/web/dist/index.html" >&2
	exit 1
}

# Dependencies are rebuilt on the primary with its pinned runtime uv. The
# artifact therefore contains source plus the Dell-verified SPA build only.
rm -rf node_modules apps/web/node_modules apps/api/.venv
DIST_SHA256="$(find apps/web/dist -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')"
printf '{\n  "source_sha": "%s",\n  "prepared_host": "%s",\n  "verified": true,\n  "build": true,\n  "dist_sha256": "%s"\n}\n' \
	"$SOURCE_SHA" "$(hostname -s)" "$DIST_SHA256" > release-evidence.json

echo "prepared verified release $SOURCE_SHA at $OUTPUT"
