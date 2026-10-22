#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cleanup() { kill "${API_PROCESS:-}" "${WEB_PROCESS:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
(cd "$ROOT_DIR/backend" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API_PROCESS=$!
(cd "$ROOT_DIR/frontend" && exec node node_modules/next/dist/bin/next dev --hostname 0.0.0.0) &
WEB_PROCESS=$!
wait -n "$API_PROCESS" "$WEB_PROCESS"
