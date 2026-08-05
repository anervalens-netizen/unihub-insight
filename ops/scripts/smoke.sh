#!/usr/bin/env bash
set -euo pipefail

PUBLIC_URL="${1:-https://insight.unihub.ro}"
LOCAL_API_SOCKET="${2:-/run/unihub-insight/api.sock}"
EXPECTED_SHA="${3:-}"
if [[ -z "$EXPECTED_SHA" && -f /opt/unihub-insight/current/SOURCE_SHA ]]; then
  EXPECTED_SHA="$(</opt/unihub-insight/current/SOURCE_SHA)"
fi

wait_for_status() {
  local path="$1"
  local expected="$2"

  for _attempt in {1..30}; do
    if curl --fail --silent --max-time 2 --unix-socket "$LOCAL_API_SOCKET" \
      "http://localhost$path" | grep -q "$expected"; then
      return 0
    fi
    sleep 1
  done

  echo "timed out waiting for $LOCAL_API_SOCKET$path" >&2
  return 1
}

wait_for_status "/livez" '"status":"ok"'
wait_for_status "/readyz" '"status":"ready"'
status="$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "$PUBLIC_URL/")"
[[ "$status" =~ ^(200|3[0-9][0-9])$ ]] || {
  echo "public SPA returned HTTP $status" >&2
  exit 1
}

[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "missing exact expected source SHA for public build verification" >&2
  exit 1
}
public_sha="$(
  curl --fail --silent --show-error --max-time 5 "$PUBLIC_URL/build-info.json" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("source_sha", ""))'
)"
[[ "$public_sha" == "$EXPECTED_SHA" ]] || {
  echo "public build SHA mismatch" >&2
  exit 1
}

for path in /livez /readyz /metrics /docs /redoc /openapi.json; do
  status="$(curl --silent --show-error --max-time 5 --output /dev/null --write-out '%{http_code}' "$PUBLIC_URL$path")"
  [[ "$status" == 404 ]] || {
    echo "public diagnostic $path returned HTTP $status" >&2
    exit 1
  }
done

echo "smoke complete: $PUBLIC_URL"
