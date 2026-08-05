#!/usr/bin/env bash
set -euo pipefail

PUBLIC_URL="${1:-https://insight.unihub.ro}"
LOCAL_API="${2:-http://172.23.0.1:8100}"

curl --fail --silent --show-error --max-time 5 "$LOCAL_API/livez" \
  | grep -q '"status":"ok"'
curl --fail --silent --show-error --max-time 5 "$LOCAL_API/readyz" \
  | grep -q '"status":"ready"'
status="$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "$PUBLIC_URL/")"
[[ "$status" =~ ^(200|3[0-9][0-9])$ ]] || {
  echo "public SPA returned HTTP $status" >&2
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
