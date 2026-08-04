#!/usr/bin/env bash
set -euo pipefail

PUBLIC_URL="${1:-https://insight.unihub.ro}"
LOCAL_API="${2:-http://127.0.0.1:8100}"

curl --fail --silent --show-error --max-time 5 "$LOCAL_API/livez" \
  | grep -q '"status":"ok"'
curl --fail --silent --show-error --max-time 5 "$LOCAL_API/readyz" \
  | grep -q '"status":"ready"'
curl --fail --silent --show-error --max-time 10 --head "$PUBLIC_URL/" >/dev/null

echo "smoke complete: $PUBLIC_URL"
