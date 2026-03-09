# OpenClaw Automation Kit — Agent Instructions

## Getting Latest Code
```bash
cd ~/openclaw-automation-kit && git pull origin main
```
Always pull before making changes to avoid conflicts.

## Architecture: Two Browser Runners

The system has two machines that can run browser automation:

### Mac Mini (primary) — `marcoss-mac-mini.local`
- **Chrome CDP**: port 18810 (dedicated airline-assistant profile; default for authenticated airline work)
- **Legacy Chrome CDP**: port 9222 (main Chrome profile; do not use for airline-auth runs unless explicitly needed)
- **Kit path**: `~/openclaw-automation-kit/`
- **Credentials**: macOS automation keychain (`~/Library/Keychains/automation.keychain-db`)
- **SMS 2FA**: Direct access to `~/Library/Messages/chat.db`
- **CDPLock**: `/tmp/browser_cdp_18810.lock` for the dedicated airline runner
- **Start Chrome**: `/tmp/launch_chrome_cdp.sh`

### Home-mind (secondary) — `home-mind.local` (Ubuntu)
- **Chrome CDP**: port 9226 (real Chrome via Xvfb on display :99)
- **Kit path**: `~/openclaw-automation-kit/`
- **Credentials**: File-based at `~/.credentials.json` (add new sites here)
- **SMS 2FA**: Via SSH to Mac Mini (`/tmp/read_sms_code.py`)
- **CDPLock**: `/tmp/browser_cdp_9226.lock`
- **Start Chrome**: `/tmp/start_chrome_real.sh`

## Runner Selection (automatic)

The AI agent on home-mind (`src/agent/tools.py`) can use either runner, but airline-auth work should stay on the stable cookied endpoint:

1. Prefer `mac-mini:18810` for authenticated airline searches.
2. Use `home-mind:9226` only when it has a known-good cookied session for that airline or for separate non-auth work.
3. Check the endpoint-specific lock file before attaching.
4. If the target endpoint is busy, either defer or use a different endpoint with a different user-data-dir.

Function: `search_award_flights` wrapper in `athanasoulis-ai-assistant/src/agent/tools.py`

## CDPLock Protocol

**CRITICAL**: Only one BrowserAgent can use a given CDP endpoint at a time.

- Lock file: derived from the endpoint port, for example:
  - `marcoss-mac-mini.local:18810` -> `/tmp/browser_cdp_18810.lock`
  - `home-mind.local:9226` -> `/tmp/browser_cdp_9226.lock`
- Contains: `{"pid": 12345, "started": "2026-02-16T20:31:25"}`
- The BrowserAgent acquires the lock on start and releases on exit
- If you see a lock from a dead PID, it's safe to delete
- **Never run two browser automations on the same endpoint simultaneously**

## Multi-Agent CDP Concurrency (Required)

- One agent per CDP endpoint at a time (endpoint = host + port).
- Different tabs on the same endpoint are not safe for parallel agents; they share one browser session and can race on target attach/state.
- Safe parallelism requires separate endpoints (for example mac mini `:18810` and home-mind `:9226`) or fully separate browser instances with different `--remote-debugging-port` and `--user-data-dir`.
- Claim a lock before any long run/restart, and release it when done.
- Record lock ownership and expiry in `INPROCESS.md` while a lock is held.
- If lock cannot be acquired, fail closed:
  - use alternate endpoint when available, or
  - defer execution instead of forcing concurrent use of the same endpoint.

## Key Config (.env)

Each machine's `~/openclaw-automation-kit/.env` must have:
```
OPENCLAW_USE_BROWSER_AGENT=true
OPENCLAW_BROWSER_AGENT_PATH=/path/to/src/browser
OPENCLAW_CDP_URL=http://127.0.0.1:<port>
OPENCLAW_CDP_LOCK_FILE=/tmp/browser_cdp_<port>.lock
ANTHROPIC_API_KEY=sk-ant-...
```

Mac Mini airline-auth default uses port 18810, home-mind uses port 9226.

## Running a Search

```bash
cd ~/openclaw-automation-kit
set -a && source .env && set +a
.venv/bin/python -m openclaw_automation.cli run-query \
  --query "Search United business SFO to SIN June 30 for 2 people under 250k miles"
```

## Adding Credentials for Home-mind

Home-mind uses `~/.credentials.json` instead of macOS keychain:
```json
{
  "www.united.com": {"user": "ka388724", "password": "..."},
  "www.delta.com": {"user": "9396260433", "password": "..."}
}
```

## Airline Runners

Located in `library/<airline>_award/runner.py`. Each has:
- `_goal()` — generates step-by-step instructions for the BrowserAgent
- `run()` — entry point called by the engine
- `_parse_matches()` or uses `result_extract.py` for parsing

### United (`library/united_award/runner.py`)
- Login: MileagePlus ka388724, SMS 2FA from sender 26266
- Approach: Cash URL first → click "Money + Miles" tab → re-enter date → Update
- "Remember me" checkbox instruction included in login goal

### Singapore Airlines (`library/singapore_award/runner.py`)
- Hybrid: BrowserAgent login + Playwright form fill + scrape
- KrisFlyer 8814147288, Akamai CAPTCHA risk

### Delta, AeroMexico, ANA, JetBlue
- See individual runner.py files for details

## Git Workflow
- **Branch**: each agent must work on its own topic branch (`codex/*`, `claude/*`, `gemini/*`)
- **Commit**: include what changed and test results
- **Push**: push your branch and open/update a PR; do not commit directly to `main`

## CI Gate (Required)
- If CI fails on your branch or on `main` for your changes, fixing CI is blocking work.
- Run lint/tests locally before handoff: `ruff check .` and `pytest`.
- Do not hand off or merge while required CI checks are red.
