#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "Install Python 3.12+ to start FlowCast."; exit 1; }
command -v npm >/dev/null || { echo "Install Node.js 22.12+ to start FlowCast."; exit 1; }
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
requirements_hash="$(shasum backend/requirements.txt | cut -d ' ' -f 1)"
if [ ! -f .venv/flowcast-requirements ] || [ "$(cat .venv/flowcast-requirements)" != "$requirements_hash" ]; then
  .venv/bin/python -m pip install -r backend/requirements.txt
  echo "$requirements_hash" > .venv/flowcast-requirements
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi
(cd frontend && npm run build)
echo "FlowCast is starting at http://127.0.0.1:8000"
echo "The first launch trains the demo forecast model automatically."
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "${PORT:-8000}"
