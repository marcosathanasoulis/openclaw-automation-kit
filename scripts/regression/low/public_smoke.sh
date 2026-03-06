#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

echo "[low] Running public no-login smoke"
./scripts/e2e_no_login_smoke.sh

echo "[low] PASS"
