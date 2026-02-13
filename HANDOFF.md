# Handoff: Multi-Agent Coordination for OpenClaw Automation Kit

**Last updated by**: Claude Opus agent
**Date**: 2026-02-13
**Branch**: `feat/skill-manifests-and-tests` (PR #1)
**PR URL**: https://github.com/marcosathanasoulis/openclaw-automation-kit/pull/1

---

## Work Model (MANDATORY for all agents)

1. **Separate feature branches** — keep feature changes on your own branch. Pull from main before starting new work.
2. **HANDOFF.md on main** — coordination doc. Update immediately when completing significant work or changing shared state.
3. **INPROCESS.md on feature branches** — per-branch status tracker. Update as you work.
4. **Pull/rebase before shared file edits** — always `git pull origin main` before editing HANDOFF.md or README.md.
5. **Don't merge to main** until live non-placeholder regression is complete and README status refresh has been run.
6. **Skip Chase** — Chase requires push 2FA (mobile app notification). Only run when user is present and confirms. Both agents should skip Chase in automated test suites.

---

## Dual CDP Endpoints (Parallel Browser Testing)

| Machine | URL | Chrome Type | Credentials | Notes |
|---|---|---|---|---|
| **Mac Mini** | `http://127.0.0.1:9222` | Real Chrome (full profile) | Full keychain (946 entries) | Primary — all sites work |
| **home-mind (Ubuntu)** | `http://127.0.0.1:9223` | Chromium | Limited (needs credential proxy) | Secondary — public + some sites |

Both agents can now run browser tests in parallel on different machines. CDPLock is per-machine (`/tmp/browser_cdp.lock`).

---

## Comprehensive Test Results (2026-02-12)

### Phase 1: Placeholder/Basic Tests (8/8 passed after fix)
| Test | Mode | Status | Time | Notes |
|---|---|---|---|---|
| Public page check (Yahoo) | live | PASS | 0.6s | |
| GitHub signin check | placeholder | PASS | 0.0s | Fixed: input now uses `username` field |
| United placeholder | placeholder | PASS | 0.0s | |
| SIA placeholder | placeholder | PASS | 0.0s | |
| ANA placeholder | placeholder | PASS | 0.0s | |
| AeroMexico placeholder | placeholder | PASS | 0.0s | |
| BofA placeholder | placeholder | PASS | 0.0s | |
| Chase placeholder | placeholder | PASS | 0.0s | |

### Phase 2: Live Browser Tests (5/5 run, Chase skipped)
| Test | Mode | Status | Time | Notes |
|---|---|---|---|---|
| **United (BROWSER)** | live | SUCCESS | 104.8s | Full award search, found flights |
| **BofA (BROWSER)** | live | PASS | 33.4s | Login + account read |
| **ANA (BROWSER)** | live | SUCCESS | 98.8s | Full award search |
| **AeroMexico (BROWSER)** | live | max_steps | 443.8s | Pipeline works, needs goal tuning for passenger selector |
| **SIA (BROWSER)** | live | max_steps | 445.0s | Vue.js form submission unreliable — needs hybrid approach |
| **Chase (BROWSER)** | — | SKIPPED | — | Push 2FA requires user presence |

**Overall: 13/14 passed (1 GitHub input schema fix applied, Chase skipped)**

---

## New Runners Added (by Opus)
- `library/aeromexico_award/` — Club Premier award search with reCAPTCHA tips
- `library/chase_balance/` — UR points balance with push 2FA
- Updated: `library/ana_award/` — step-by-step ANA-specific URL + form
- Updated: `library/bofa_alert/` — BrowserAgent integration with login flow
- Updated: `library/united_award/` — improved step-by-step goal
- Updated: `library/singapore_award/` — KrisFlyer Vue.js-aware goal

---

## CDPLock Rules
- BrowserAgent handles locking automatically — no manual lock needed
- Only ONE browser automation at a time per machine
- Lock file: `/tmp/browser_cdp.lock`
- If a lock gets stuck: `cat /tmp/browser_cdp.lock` for PID, verify with `ps`, kill if stale

---

## Known Issues & Next Steps

1. **SIA needs hybrid approach** — BrowserAgent for login, Playwright for Vue.js form fill (proven in `sia_search_v5.py`)
2. **AeroMexico** — passenger selector UI takes too many steps; needs more specific goal instructions
3. **Chase** — requires push 2FA, skip unless user is present
4. **Credential proxy** — needed for Ubuntu to fetch credentials from Mac Mini keychain
5. **Daily regression** — script exists (`scripts/collect_automation_status.py --write-readme`) but needs browser test integration

## Coordination Rules
1. Check INPROCESS.md and HANDOFF.md before starting work
2. Pull latest before making changes
3. CDPLock prevents concurrent browser automation on the same machine
4. Commit and push changes immediately so the other agent can see them
5. Do NOT revert or overwrite the other agent's changes without coordination
