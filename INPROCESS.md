# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.

## Current Work

- **claude/daily-award-scan** (Claude Opus agent, Feb 16-17)
  - Task: Daily automated award search for June 2026 across 6 airlines
  - Commits on main: 2ac377c..c623020 (runners, daily scan, lint, multiple fixes)
  - Status: PARTIALLY WORKING — 3 of 6 airlines producing results
  - Results (Feb 17 overnight):
    - SIA: 8 matches, best 44,000 miles SFO-SIN (WORKING)
    - JetBlue: 5 matches SFO-NRT (WORKING)
    - Delta: 7 matches earlier (13,500 best), but results page crashes Chrome on retest
    - ANA: Login wall + site crashes Chrome (needs ANA-specific approach)
    - AeroMexico: Form too complex, 0 matches (Spanish site with toggle)
    - United: Rate limited from earlier testing, shows USD only
  - Fixes applied: Delta login-first, ANA login, SIA agent-only fallback, js_eval extraction
  - Known issues: Delta/ANA results pages crash Chrome (too heavy for CDP)
  - Launchd: `com.athanasoulis.daily-award-search` scheduled 6 AM daily on Mac Mini
  - Screenshots: `~/openclaw-automation-kit/debug_screenshots/` on Mac Mini

- `codex/agent-ci-gate-rules`
  - Task: update agent instruction files to require branch isolation and mandatory CI fixes before handoff/merge.
  - Files: `AGENTS.md`, `CLAUDE.md`, `codex.md`, `INPROCESS.md`
  - Status: complete (`ruff check .` clean; `pytest` 30 passed)

- `codex/skill-confidence-v106`
  - Task: harden marketplace-facing skill docs for trust boundaries and safe defaults.
  - Files: `skills/openclaw-web-automation/SKILL.md`, `skills/openclaw-web-automation/setup.json`
  - Status: complete (docs hardened, tests/smoke passed)

- `codex/update-skill-description`
  - Task: update marketplace skill description text and publish patch release.
  - Files: `skills/openclaw-web-automation/SKILL.md`
  - Status: complete (description updated; pending publish + merge)

- `codex/fix-award-extraction-gap`
  - Added structured `MATCH|...` extraction path and fallback parsing.
  - Added no-login library automations:
    - `library/site_headlines`
    - `library/site_text_watch`
  - Added local demo canned flows:
    - `Run headlines demo`
    - `Run text watch demo`
    - `Run captcha demo`
    - `Run 2FA demo`
  - Added no-login E2E smoke script + CI workflow.

## Release coordination note (Codex)

- PR `#5` had failing `E2E No-Login Smoke` due missing demo test dependencies in smoke env.
- Fixed by switching smoke setup from `requirements.txt` to `requirements-dev.txt` in:
  - `scripts/e2e_no_login_smoke.sh`
- Local re-run passed end-to-end.

## Coordination Rules

- Update this file when starting/stopping long runs.
- Keep entries concise: `owner`, `task`, `resource`, `status`.
- Move durable info to `HANDOFF.md`; keep this file operational.
- Commit and push frequently so parallel agents can see latest state.
