#!/bin/bash
cd /tmp/openclaw-automation-kit
set -a
source ~/athanasoulis-ai-assistant/.env
set +a
export OPENCLAW_USE_BROWSER_AGENT=true
export OPENCLAW_BROWSER_AGENT_MODULE=browser_agent
export OPENCLAW_BROWSER_AGENT_PATH=~/athanasoulis-ai-assistant/src/browser
export OPENCLAW_CDP_URL=http://127.0.0.1:9222
export PYTHONUNBUFFERED=1
export OPENCLAW_RUNNER_TIMEOUT_SECONDS=900
exec ~/athanasoulis-ai-assistant/.venv/bin/python full_test_suite.py
