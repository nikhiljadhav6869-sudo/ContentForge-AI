#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT_DIR/.data"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.data/uv-cache}"
export npm_config_cache="${npm_config_cache:-$ROOT_DIR/.data/npm-cache}"
cd "$ROOT_DIR/backend"
uv sync --frozen
.venv/bin/alembic upgrade head
.venv/bin/python -m app.init_checkpoints
cd "$ROOT_DIR/frontend"
npm ci --no-audit --no-fund
