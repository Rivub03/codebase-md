#!/usr/bin/env bash
# Create the venv on first run, then start the API with reload enabled.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

[ -f .env ] || cp .env.example .env
exec ./.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT:-8080}"
