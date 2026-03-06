#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

echo "[medium] Running core flow regression tests"
pytest -q \
  tests/test_human_loop_example.py \
  tests/test_engine_envelope.py

echo "[medium] PASS"
