# In-Process: Skill Testing Coordination

**Agents**: Claude Opus (this file's author) + Codex (other agent)
**Branch**: `feat/skill-manifests-and-tests`
**Repo on Mac Mini**: `/tmp/openclaw-automation-kit` (already cloned, 32 tests passing)

---

## CRITICAL FIX: Double-Lock Bug (commit 8b58824)

`browser_agent_adapter.py` was deadlocking — it acquired CDPLock, then BrowserAgent._start_browser() tried the same lock. Fixed: adapter no longer locks. BrowserAgent handles its own locking.

**Codex**: Pull latest on the PR branch before testing: `git pull origin feat/skill-manifests-and-tests`

---

## Test Assignments

### Opus (done):
- [x] Credential resolution pipeline (env vars + keychain) — PASS
- [x] public_page_check with live Yahoo.com — PASS
- [x] github_signin_check with credential_refs — PASS
- [x] Skill-level runner invocation — PASS
- [x] 32 unit tests all passing

### Codex (TODO — real Chrome browser tests on Mac Mini):
- [ ] **United award search** via `library/united_award` with BrowserAgent
- [ ] **SIA award search** via `library/singapore_award` with BrowserAgent
- [ ] **ANA award search** via `library/ana_award` with BrowserAgent

---

## Mac Mini Setup for Browser Tests

```bash
# Pull latest:
cd /tmp/openclaw-automation-kit
git pull origin feat/skill-manifests-and-tests

# Reinstall:
~/athanasoulis-ai-assistant/.venv/bin/pip install -e '.[dev]' -q

# Set environment:
export OPENCLAW_USE_BROWSER_AGENT=true
export OPENCLAW_BROWSER_AGENT_MODULE=browser_agent
export OPENCLAW_BROWSER_AGENT_PATH=~/athanasoulis-ai-assistant/src/browser
export OPENCLAW_CDP_URL=http://127.0.0.1:9222
export ANTHROPIC_API_KEY=<your-key>

# Run a test via the engine:
~/athanasoulis-ai-assistant/.venv/bin/python -c "
import os, json, sys
sys.path.insert(0, 'src')
from pathlib import Path
from openclaw_automation.engine import AutomationEngine
root = Path('.')
engine = AutomationEngine(root)
result = engine.run(root / 'library' / 'united_award', {
    'from': 'SFO', 'to': ['NRT'], 'days_ahead': 14,
    'max_miles': 120000, 'travelers': 1, 'cabin': 'business',
})
print(json.dumps(result, indent=2))
"
```

## CDPLock
- BrowserAgent handles locking automatically — no manual lock needed
- Only ONE browser automation at a time on Mac Mini
- Lock file: `/tmp/browser_cdp.lock`
- If stuck: `cat /tmp/browser_cdp.lock` to see PID, kill if stale
