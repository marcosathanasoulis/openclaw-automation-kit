# In-Process: Skill Testing Coordination

**Agents**: Claude Opus (this file author) + Codex (other agent)
**Branch**: `feat/skill-manifests-and-tests`
**Repo on Mac Mini**: `/tmp/openclaw-automation-kit` (already cloned, 34 tests passing)

---

## CRITICAL FIX: Double-Lock Bug (commit 8b58824)

`browser_agent_adapter.py` was deadlocking. Fixed: adapter no longer locks. BrowserAgent handles its own locking.

---

## Test Assignments

### Opus:
- [x] Credential resolution pipeline (env vars + keychain) -- PASS
- [x] public_page_check with live Yahoo.com -- PASS
- [x] github_signin_check with credential_refs -- PASS
- [x] Skill-level runner invocation -- PASS
- [x] 34 unit tests all passing (merged Codex PR #2 changes)
- [x] Resolved merge conflict (adapter double-lock vs Codex re-adding lock)
- [x] **United BrowserAgent test #1** (1 traveler) -- pipeline works, hit 60 steps on travelers UI bug
- [x] **United BrowserAgent test #2** (2 travelers) -- pipeline works, search executed (SFO-NRT Apr 15 Business), SSH dropped at step 17 before reading results
- [x] CDPLock validated: my test waited 85s while Codex held lock, then acquired automatically
- [ ] **United BrowserAgent test #3** (2 travelers, nohup) -- in progress, waiting for CDPLock

### Codex:
- [x] **United award to CDG** -- ran via `openclaw_automation.cli run`
- [x] **SIA award search** -- currently running (PID 45370)
- [ ] **ANA award search** -- TODO

### Key findings:
- **CDPLock works across agents** -- my test waited while Codex had the lock, acquired when released
- **Stale lock detection works** -- PID checks prevent stuck locks
- **SSH timeout issue** -- long-running browser tests drop SSH. Use nohup or tmux for > 2min tests
- **United travelers UI bug** -- button text shows 2 Adults even after changing to 1 in dialog

---

## CDPLock
- BrowserAgent handles locking automatically
- Only ONE browser automation at a time on Mac Mini
- Lock file: `/tmp/browser_cdp.lock`
- If stuck: `cat /tmp/browser_cdp.lock` to see PID, kill if stale
