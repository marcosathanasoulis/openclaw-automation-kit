#!/bin/bash
set -euo pipefail
cd /tmp/openclaw-automation-kit

KEY=""
for pid in $(pgrep -f 'full_test_suite.py|openclaw_automation.cli run|run_sin_tests.py' || true); do
  line=$(ps eww -p "$pid" | tail -n 1 || true)
  if echo "$line" | grep -q 'ANTHROPIC_API_KEY='; then
    KEY=$(echo "$line" | sed -n 's/.*ANTHROPIC_API_KEY=\([^ ]*\).*/\1/p')
    break
  fi
done

if [ -z "$KEY" ]; then
  echo '[codex] missing ANTHROPIC_API_KEY source process' >&2
  exit 2
fi

echo '[codex] waiting for /tmp/browser_cdp.lock to clear...'
while [ -f /tmp/browser_cdp.lock ]; do sleep 5; done

export OPENCLAW_USE_BROWSER_AGENT=true
export OPENCLAW_BROWSER_AGENT_MODULE=browser_agent
export OPENCLAW_BROWSER_AGENT_PATH=/Users/marcos/athanasoulis-ai-assistant/src/browser
export OPENCLAW_CDP_URL=http://127.0.0.1:9222
export ANTHROPIC_API_KEY="$KEY"

run_case () {
  local name="$1"
  local script_dir="$2"
  local input_json="$3"
  echo "[codex] running $name"
  /Users/marcos/athanasoulis-ai-assistant/.venv/bin/python -m openclaw_automation.cli run \
    --script-dir "$script_dir" \
    --input "$input_json" \
    > "/tmp/codex_${name}.json" 2> "/tmp/codex_${name}.err" || true
  echo "[codex] done $name"
}

run_case united library/united_award '{"from":"SFO","to":["CDG"],"days_ahead":30,"max_miles":120000,"travelers":2,"cabin":"business"}'
run_case sia library/singapore_award '{"from":"SFO","to":["SIN"],"days_ahead":30,"max_miles":120000,"travelers":2,"cabin":"business"}'
run_case ana library/ana_award '{"from":"SFO","to":["HND"],"days_ahead":30,"max_miles":120000,"travelers":2,"cabin":"business"}'

echo '[codex] complete'
