#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x ".venv/bin/python3" ]]; then
  .venv/bin/python3 run_server.py
else
  python3 run_server.py
fi
