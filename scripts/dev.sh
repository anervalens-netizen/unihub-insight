#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

${UNIHUB_INSIGHT_API_COMMAND:-npm run dev:api} &
API_PID=$!
${UNIHUB_INSIGHT_WEB_COMMAND:-npm run dev:web}
