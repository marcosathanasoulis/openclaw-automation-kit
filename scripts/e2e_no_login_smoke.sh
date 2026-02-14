#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install -q -r requirements-dev.txt
python -m pip install -q -e .

echo "[1/5] Lint + unit tests"
ruff check .
pytest -q

echo "[2/5] Manifest validation"
python -m openclaw_automation.cli validate --script-dir examples/public_page_check >/dev/null
python -m openclaw_automation.cli validate --script-dir library/united_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/singapore_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/ana_award >/dev/null
python -m openclaw_automation.cli validate --script-dir library/bofa_alert >/dev/null
python -m openclaw_automation.cli validate --script-dir library/github_signin_check >/dev/null
python -m openclaw_automation.cli validate --script-dir library/site_headlines >/dev/null
python -m openclaw_automation.cli validate --script-dir library/site_text_watch >/dev/null

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
python skills/openclaw-web-automation-basic/scripts/run_query.py \
  --query "Open https://www.wikipedia.org and count mentions of encyclopedia" >/tmp/openclaw_skill_web.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/openclaw_skill_web.json").read_text())
assert payload["ok"] is True
assert payload["script_id"] == "web.public_page_check"
print("skill_web_ok")
PY

echo "[5/5] Skill script smoke (award placeholder path)"
python skills/openclaw-award-search/scripts/run_query.py \
  --query "Search United award travel economy from SFO to AMS in next 30 days under 120k miles" >/tmp/openclaw_skill_award.json
python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/openclaw_skill_award.json").read_text())
assert payload["status"]["ok"] is True
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

echo "E2E no-login smoke passed."
