#!/bin/bash
# Wrapper script for daily award scan — sources .env and runs the kit-based scan
# Disabled by default; require explicit opt-in for scheduled runs.
set -euo pipefail

if [[ "${OPENCLAW_ENABLE_DAILY_AWARD_SCAN:-false}" != "true" ]]; then
  echo "Daily award scan disabled; set OPENCLAW_ENABLE_DAILY_AWARD_SCAN=true to enable scheduled runs." >&2
  exit 0
fi

set -a
source /Users/marcos/openclaw-automation-kit/.env
set +a

export PYTHONUNBUFFERED=1

cd /Users/marcos/openclaw-automation-kit
exec /Users/marcos/openclaw-automation-kit/.venv/bin/python \
    scripts/daily_award_scan.py --send-report "$@"
