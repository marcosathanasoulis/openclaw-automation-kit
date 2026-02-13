# In-Process: Skill Testing Coordination

**Agents**: Claude Opus (this file author) + Codex (other agent)
**Branch**: `feat/skill-manifests-and-tests` (PR #1)
**Repo on Mac Mini**: `/tmp/openclaw-automation-kit` (34 tests passing, CI green)

---

## Test Results

### Opus:
- [x] Credential resolution pipeline (env vars + keychain) -- PASS
- [x] public_page_check with live Yahoo.com -- PASS
- [x] github_signin_check with credential_refs -- PASS
- [x] Skill-level runner invocation -- PASS
- [x] 34 unit tests all passing (merged Codex PR #2 changes)
- [x] Resolved merge conflict (adapter double-lock vs Codex re-adding lock)
- [x] **United BrowserAgent test #1** (1 traveler) -- pipeline works, hit 60 steps on travelers UI bug
- [x] **United BrowserAgent test #2** (2 travelers) -- pipeline works, search executed, SSH dropped at step 17
- [x] **United BrowserAgent test #3** (2 travelers, nohup) -- FULL SUCCESS: 14 steps, 151s
  - Navigated united.com, enabled miles, set SFO-NRT Apr 15, Business, 2 Adults
  - Filtered mixed cabin, sorted by business miles
  - Correctly reported "stuck" -- all flights 250K+ miles (over 120K max)
  - Engine envelope: ok=true, real_data=true, mode=live, matches=[]
- [x] CDPLock validated: waited 85s for Codex lock, acquired when released

### Codex:
- [x] **United award to CDG** -- ran via `openclaw_automation.cli run`
- [x] **SIA award search** -- completed (PID 45370)
- [ ] **ANA award search** -- TODO

### Key findings:
- **Full pipeline validated**: engine -> runner -> BrowserAgent adapter -> Chrome CDP -> results
- **CDPLock works across agents** -- waited while Codex had the lock, acquired when released
- **Stale lock detection works** -- PID checks prevent stuck locks
- **SSH timeout workaround**: use nohup for tests > 2 min
- **ANTHROPIC_API_KEY must be in env** when running via nohup (not inherited from SSH session)
- **United travelers UI bug**: button text shows 2 Adults even after changing to 1 in dialog
- **Result extraction gap**: BrowserAgent reports stuck/done but does not extract structured match data from the page

---

## Remaining Work

1. **ANA browser test** -- not yet attempted
2. **Result extraction**: BrowserAgent returns status but not structured flight data (matches always [])
3. **PR merge**: CI green, tests passing, ready for merge when all browser tests done

---

## CDPLock
- BrowserAgent handles locking automatically
- Only ONE browser automation at a time on Mac Mini
- Lock file: `/tmp/browser_cdp.lock`
- If stuck: `cat /tmp/browser_cdp.lock` to see PID, kill if stale
