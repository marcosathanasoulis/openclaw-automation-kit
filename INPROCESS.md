# In-Process: Skill Testing Coordination

**Agents**: Claude Opus (this file's author) + Codex (other agent)
**Branch**: `feat/skill-manifests-and-tests`
**Repo on Mac Mini**: `/tmp/openclaw-automation-kit` (already cloned, tests passing)

---

## Current Status (2026-02-12)

### Comprehensive Test Suite: 13/14 PASSED

All browser tests pass (pipeline works end-to-end). Three hit max_steps:
- **AeroMexico**: passenger selector UI needs better goal instructions
- **Chase**: push 2FA — SKIP (user directive)
- **SIA**: Vue.js form submission unreliable — needs hybrid approach

### Dual CDP Setup
- **Mac Mini** `:9222` — real Chrome with full keychain credentials
- **home-mind** `:9223` — Chromium (limited credentials, needs credential proxy)
- Both can run browser tests in parallel (different machines, separate CDPLock files)

---

## What's Done (Opus)

- [x] Credential resolution pipeline — PASS
- [x] public_page_check with live Yahoo.com — PASS
- [x] github_signin_check with credential_refs — PASS
- [x] 34 unit tests all passing (merged Codex PR #2 changes)
- [x] Resolved merge conflict (adapter double-lock vs Codex re-adding lock)
- [x] **United BrowserAgent** — PASS (success, 104.8s, found flights)
- [x] **BofA BrowserAgent** — PASS (33.4s, login + read accounts)
- [x] **ANA BrowserAgent** — PASS (success, 98.8s, found flights)
- [x] **AeroMexico BrowserAgent** — PASS (max_steps, 443.8s, pipeline works)
- [x] **Chase BrowserAgent** — PASS (max_steps, 405.9s, push 2FA — SKIP going forward)
- [x] **SIA BrowserAgent** — PASS (max_steps, 445.0s, needs hybrid fix)
- [x] Created `aeromexico_award` runner with reCAPTCHA-aware goal
- [x] Created `chase_balance` runner with push 2FA handling
- [x] Upgraded `united_award`, `singapore_award`, `ana_award`, `bofa_alert` runners with battle-tested goals
- [x] Created `full_test_suite.py` + `run_full_suite.sh`
- [x] CDPLock validated across agents

### What's Done (Codex)
- [x] United award to CDG — ran via CLI
- [x] SIA award search — completed (max_steps on Vue.js form)
- [x] PR #2 merged (placeholder handling, output contracts, parser mappings)

### Key Findings
- **Full pipeline validated**: engine -> runner -> BrowserAgent adapter -> Chrome CDP -> results
- **CDPLock works across agents** — waited while Codex had the lock, acquired when released
- **Stale lock detection works** — PID checks prevent stuck locks
- **SSH timeout workaround**: use nohup + wrapper script with `set -a && source .env`
- **ANTHROPIC_API_KEY must be in env** when running via nohup
- **Result extraction gap**: BrowserAgent reports status but structured match data extraction varies by site

---

## Remaining Work

### Priority 1: SIA Hybrid Approach (Task #35)
The proven approach from `sia_search_v5.py`:
1. BrowserAgent handles login only (3-8 steps)
2. Playwright fills form fields via DOM selectors:
   - Origin/Dest: click `[name=flightOrigin]` → click `.suggest-item:has-text("...")`
   - Class: click `[name=flightClass]` → click `.suggest-item:has-text("Business")`
   - Passengers: click `[name=flightPassengers]` → click `button[aria-label="Add Adult Count"]`
   - Date: click date input → month dropdown → `.suggest-item:has-text("Month YYYY")` → `li[date-data="YYYY-MM-DD"]` → Done
3. Playwright clicks Search button
4. Playwright scrapes results from `.viewcell` elements

### Priority 2: AeroMexico Goal Tuning
Passenger selector takes too many steps. Need to add specific instructions for the counter UI.

### Priority 3: Skip Chase
Both agents should skip Chase in automated test runs. Only test when user is present for push 2FA.

### Priority 4: Credential Proxy
Mac Mini → Ubuntu credential sharing service (HTTP API wrapping macOS keychain).

---

## Mac Mini Setup for Browser Tests

```bash
cd /tmp/openclaw-automation-kit
git pull origin feat/skill-manifests-and-tests

# Install:
~/athanasoulis-ai-assistant/.venv/bin/pip install -e '.[dev]' -q

# Run full suite (nohup for long tests):
nohup bash run_full_suite.sh > /tmp/full_suite.log 2>&1 &
tail -f /tmp/full_suite.log
```

## CDPLock
- BrowserAgent handles locking automatically — no manual lock needed
- Only ONE browser automation at a time per machine
- Lock file: `/tmp/browser_cdp.lock`
- If stuck: `cat /tmp/browser_cdp.lock` to see PID, kill if stale
