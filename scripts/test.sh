#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"
.venv/bin/ruff check app tests
.venv/bin/pytest -q
cd "$ROOT_DIR/frontend"
npm run typecheck
npm run build
