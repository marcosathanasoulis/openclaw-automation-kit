#!/usr/bin/env bash
# OpenClaw health-check launch wrapper for macOS launchd.
#
# Loads secrets from the macOS login Keychain at runtime instead of storing
# them in cleartext inside the launchd plist. Mirrors the pattern used by
# athanasoulis-ai-assistant/scripts/run_united_award_monitor.sh and
# src/connectors/imessage/sync_wrapper.sh.

set -euo pipefail

WORK_DIR="${OPENCLAW_WORK_DIR:-${HOME}/openclaw-automation-kit}"
VENV_PY="${OPENCLAW_PYTHON:-${WORK_DIR}/.venv/bin/python}"

# Load a secret from the Keychain into an env var if not already set.
# Usage: load_keychain_var VAR_NAME service_name [account_name]
load_keychain_var() {
  local var_name="$1"
  local service_name="$2"
  local account_name="${3:-assistant}"
  if [[ -n "${!var_name:-}" ]]; then
    return 0
  fi
  if command -v security >/dev/null 2>&1; then
    local value
    value="$(security find-generic-password -s "$service_name" -a "$account_name" -w 2>/dev/null || true)"
    if [[ -n "$value" ]]; then
      export "$var_name=$value"
    fi
  fi
}

load_keychain_var ANTHROPIC_API_KEY assistant/anthropic_api_key assistant
load_keychain_var BOT_SEND_TOKEN assistant/openclaw_health_bot_send_token assistant
load_keychain_var AUTOMATION_KEYCHAIN_PASSWORD assistant/automation_keychain_password assistant

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

if [[ ! -x "$VENV_PY" ]]; then
  echo "OpenClaw Python venv not found at $VENV_PY" >&2
  exit 1
fi

cd "$WORK_DIR"
exec "$VENV_PY" -m openclaw_automation.cli doctor --json
