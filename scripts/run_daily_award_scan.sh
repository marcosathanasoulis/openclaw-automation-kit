#!/bin/bash
# Wrapper script for daily award scan — sources .env and runs the kit-based scan
set -a
source /Users/marcos/openclaw-automation-kit/.env
set +a

export PYTHONUNBUFFERED=1

cd /Users/marcos/openclaw-automation-kit
exec /Users/marcos/openclaw-automation-kit/.venv/bin/python \
    scripts/daily_award_scan.py --send-report "$@"
