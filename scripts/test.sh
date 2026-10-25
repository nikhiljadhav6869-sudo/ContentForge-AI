#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"
.venv/bin/ruff check app tests
.venv/bin/ruff check ../scripts/backup.py ../scripts/scheduled_backup.py ../scripts/configure_backup_schedule.py ../scripts/configure_production.py ../scripts/check_deployment.py ../scripts/smoke.py
.venv/bin/pytest -q
cd "$ROOT_DIR/frontend"
npm run typecheck
npm run build
