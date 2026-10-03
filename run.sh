#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ../../.venv/bin/uvicorn api.server:app --host 127.0.0.1 --port 8004
