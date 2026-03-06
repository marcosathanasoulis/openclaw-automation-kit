#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

./scripts/regression/critical/security_gate.sh
./scripts/regression/medium/core_flows.sh
./scripts/regression/low/public_smoke.sh

echo "[regression] ALL PASS"

