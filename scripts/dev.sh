#!/usr/bin/env bash
# Start PMIP: build frontend + run API on http://localhost:8000
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

lsof -ti:8000 | xargs kill -9 2>/dev/null || true

export PYTHONPATH=src
echo "Building frontend..."
(cd frontend && npm run build)

echo "Starting API at http://localhost:8000"
exec .venv/bin/python -m uvicorn pmip.api.main:app --host 0.0.0.0 --port 8000 --reload
