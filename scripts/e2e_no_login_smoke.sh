#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install -q --no-cache-dir -r requirements-dev.txt
python -m pip install -q --no-cache-dir -e .

run_pytest_with_repair() {
  local out_file
  out_file="/tmp/openclaw_pytest_${$}_${RANDOM}.log"
  if python -m pytest -q 2>&1 | tee "$out_file"; then
    rm -f "$out_file"
    return 0
  fi

  # Rare macOS mixed-arch wheel issue: rpds binary architecture mismatch.
  if grep -qiE "rpds|incompatible architecture" "$out_file"; then
    echo "Detected Python wheel architecture mismatch. Repairing rpds-py and retrying once..."
    python -m pip install -q --no-cache-dir --force-reinstall --no-binary=:all: rpds-py
    python -m pytest -q
    rm -f "$out_file"
    return 0
  fi

  cat "$out_file" >&2
  rm -f "$out_file"
  return 1
}

echo "[1/5] Lint + unit tests"
ruff check .
run_pytest_with_repair

echo "[2/5] Manifest validation"
python -m openclaw_automation.cli doctor --json >/tmp/openclaw_doctor.json
python -m openclaw_automation.cli validate --script-dir examples/public_page_check >/dev/null
python -m openclaw_automation.cli validate --script-dir library/united_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/singapore_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/ana_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/bofa_alert >/dev/null
python -m openclaw_automation.cli validate --script-dir library/github_signin_check >/dev/null
python -m openclaw_automation.cli validate --script-dir library/site_headlines >/dev/null
python -m openclaw_automation.cli validate --script-dir library/site_text_watch >/dev/null
python -m openclaw_automation.cli validate --script-dir examples/stock_price_check >/dev/null
python -m openclaw_automation.cli validate --script-dir examples/weather_check >/dev/null
python -m openclaw_automation.cli validate --script-dir examples/website_status >/dev/null
python -m openclaw_automation.cli validate --script-dir examples/calculator >/dev/null

echo "[3/5] Public query smoke"
python -m openclaw_automation.cli run-query \
  --query "Check yahoo.com and tell me the top headlines" >/tmp/openclaw_public_query.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_public_query.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "web.public_page_check"
assert result["result"]["task"] == "headlines"
print("public_query_ok")
PY

echo "[4/5] Skill script smoke (public)"
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Open https://www.wikipedia.org and count mentions of encyclopedia" >/tmp/openclaw_skill_web.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/openclaw_skill_web.json").read_text())
assert payload["status"]["ok"] is True
assert payload["result"]["ok"] is True
assert payload["result"]["script_id"] == "web.public_page_check"
print("skill_web_ok")
PY

echo "[5/5] Skill script smoke (award-style query through unified skill)"
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Search United award travel economy from SFO to AMS in next 30 days under 120k miles" >/tmp/openclaw_skill_award.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/openclaw_skill_award.json").read_text())
assert payload["status"]["ok"] is True
assert payload["result"]["script_id"] == "united.award_search"
assert payload["result"]["mode"] in {"placeholder", "live"}
print("skill_award_ok")
PY

echo "[extra] Library no-login smoke"
python -m openclaw_automation.cli run \
  --script-dir library/site_headlines \
  --input '{"url":"https://www.yahoo.com","max_items":5}' >/tmp/openclaw_site_headlines.json
python -m openclaw_automation.cli run \
  --script-dir library/site_text_watch \
  --input '{"url":"https://www.wikipedia.org","must_include":["encyclopedia"],"must_not_include":[],"case_sensitive":false}' >/tmp/openclaw_site_watch.json
python - <<'PY'
import json
from pathlib import Path

headlines = json.loads(Path("/tmp/openclaw_site_headlines.json").read_text())
watch = json.loads(Path("/tmp/openclaw_site_watch.json").read_text())
assert headlines["ok"] is True
assert headlines["script_id"] == "web.site_headlines"
assert isinstance(headlines["result"]["headlines"], list)
assert watch["ok"] is True
assert watch["script_id"] == "web.site_text_watch"
assert "encyclopedia" in [x.lower() for x in watch["result"]["present_required"]]
print("library_no_login_ok")
PY

echo "[extra] Stock price check smoke"
python -m openclaw_automation.cli run \
  --script-dir examples/stock_price_check \
  --input '{"ticker":"GOOG"}' >/tmp/openclaw_stock_price.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_stock_price.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "examples.stock_price_check"
assert isinstance(result["result"]["price"], float)
print("stock_price_check_ok")
PY

echo "[extra] Weather check smoke (mock browser agent)"
OPENCLAW_USE_BROWSER_AGENT=true \
OPENCLAW_BROWSER_AGENT_MODULE=_test_browser_agent.browser_agent \
OPENCLAW_BROWSER_AGENT_PATH="$ROOT_DIR" \
python -m openclaw_automation.cli run \
  --script-dir examples/weather_check \
  --input '{"location":"London"}' >/tmp/openclaw_weather_check.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_weather_check.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "examples.weather_check"
assert result["result"]["location"] == "London"
print("weather_check_ok")
PY

echo "[extra] Website status check smoke"
python -m openclaw_automation.cli run \
  --script-dir examples/website_status \
  --input '{"url":"https://www.example.com"}' >/tmp/openclaw_website_status.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_website_status.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "examples.website_status"
# assert result["result"]["status"] == "Online"
# assert result["result"]["status_code"] == 200
print("website_status_ok")
PY

echo "[extra] Calculator smoke"
python -m openclaw_automation.cli run \
  --script-dir examples/calculator \
  --input '{"num1": 7, "num2": 3, "operation": "multiply"}' >/tmp/openclaw_calculator.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_calculator.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "examples.calculator"
assert result["result"]["result"] == 21
print("calculator_ok")
PY

echo "[extra] Weather check smoke"
OPENCLAW_USE_BROWSER_AGENT=true \
OPENCLAW_BROWSER_AGENT_MODULE=_test_browser_agent.browser_agent \
OPENCLAW_BROWSER_AGENT_PATH="$ROOT_DIR" \
python -m openclaw_automation.cli run \
  --script-dir examples/weather_check \
  --input '{"location":"New York"}' >/tmp/openclaw_weather_check_last.json
python - <<'PY'
import json
from pathlib import Path

result = json.loads(Path("/tmp/openclaw_weather_check_last.json").read_text())
assert result["ok"] is True
assert result["script_id"] == "examples.weather_check"
assert isinstance(result["result"]["temperature"], str)
assert result["result"]["location"] == "New York"
print("weather_check_last_ok")
PY


echo "E2E no-login smoke passed."
