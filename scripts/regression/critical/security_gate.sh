#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"

echo "[critical] Security gate: missing assertion must block risky run"
export OPENCLAW_SECURITY_GATE_ENABLED=true
export OPENCLAW_SECURITY_SIGNING_KEY="test-signing-key"
export OPENCLAW_SECURITY_EXPECTED_USER_ID="+14152268266"
export OPENCLAW_SECURITY_MAX_AGE_SECONDS=$((7*24*60*60))
export OPENCLAW_TOTP_SECRET="JBSWY3DPEHPK3PXP"

missing_output="$(python -m openclaw_automation.cli run \
  --script-dir "$ROOT/library/github_signin_check" \
  --input '{"username":"demo-user","credential_refs":{"password":"openclaw/github/password"},"messaging_target":{"type":"imessage","address":"+14155550123"}}' 2>&1)"
echo "$missing_output" | grep -q '"ok": false'
echo "$missing_output" | grep -q "missing security_assertion"

echo "[critical] Security gate: valid TOTP assertion must allow risky run"
totp_code="$(python - <<'PY'
from openclaw_automation.security_gate import generate_totp_code
import time
print(generate_totp_code("JBSWY3DPEHPK3PXP", int(time.time())))
PY
)"
assertion_json="$(python -m openclaw_automation.cli issue-security-assertion \
  --user-id +14152268266 \
  --totp-code "$totp_code" \
  --totp-secret-env OPENCLAW_TOTP_SECRET \
  --signing-key-env OPENCLAW_SECURITY_SIGNING_KEY)"

assertion_value="$(ASSERTION_JSON="$assertion_json" python - <<'PY'
import json
import os
print(json.dumps(json.loads(os.environ["ASSERTION_JSON"])["security_assertion"]))
PY
)"

ok_output="$(python -m openclaw_automation.cli run \
  --script-dir "$ROOT/library/github_signin_check" \
  --input "{\"username\":\"demo-user\",\"credential_refs\":{\"password\":\"openclaw/github/password\"},\"messaging_target\":{\"type\":\"imessage\",\"address\":\"+14155550123\"},\"security_assertion\":$assertion_value}")"
echo "$ok_output" | grep -q '"ok": true'

echo "[critical] Security gate: session binding mismatch must block"
export OPENCLAW_SECURITY_EXPECTED_SESSION_BINDING="mac-mini:marcos"
bad_binding_assertion_json="$(python -m openclaw_automation.cli issue-security-assertion \
  --user-id +14152268266 \
  --totp-code "$totp_code" \
  --session-binding "home-mind:marcos" \
  --totp-secret-env OPENCLAW_TOTP_SECRET \
  --signing-key-env OPENCLAW_SECURITY_SIGNING_KEY)"
bad_binding_value="$(ASSERTION_JSON="$bad_binding_assertion_json" python - <<'PY'
import json
import os
print(json.dumps(json.loads(os.environ["ASSERTION_JSON"])["security_assertion"]))
PY
)"
bad_binding_output="$(python -m openclaw_automation.cli run \
  --script-dir "$ROOT/library/github_signin_check" \
  --input "{\"username\":\"demo-user\",\"credential_refs\":{\"password\":\"openclaw/github/password\"},\"messaging_target\":{\"type\":\"imessage\",\"address\":\"+14155550123\"},\"security_assertion\":$bad_binding_value}")"
echo "$bad_binding_output" | grep -q '"ok": false'
echo "$bad_binding_output" | grep -q 'session binding mismatch'

echo "[critical] Security gate: matching session binding must allow"
good_binding_assertion_json="$(python -m openclaw_automation.cli issue-security-assertion \
  --user-id +14152268266 \
  --totp-code "$totp_code" \
  --session-binding "mac-mini:marcos" \
  --totp-secret-env OPENCLAW_TOTP_SECRET \
  --signing-key-env OPENCLAW_SECURITY_SIGNING_KEY)"
good_binding_value="$(ASSERTION_JSON="$good_binding_assertion_json" python - <<'PY'
import json
import os
print(json.dumps(json.loads(os.environ["ASSERTION_JSON"])["security_assertion"]))
PY
)"
good_binding_output="$(python -m openclaw_automation.cli run \
  --script-dir "$ROOT/library/github_signin_check" \
  --input "{\"username\":\"demo-user\",\"credential_refs\":{\"password\":\"openclaw/github/password\"},\"messaging_target\":{\"type\":\"imessage\",\"address\":\"+14155550123\"},\"security_assertion\":$good_binding_value}")"
echo "$good_binding_output" | grep -q '"ok": true'

echo "[critical] PASS"
