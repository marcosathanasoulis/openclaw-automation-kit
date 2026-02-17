# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.

## Current Work

- `codex/fix-main-ci-lint-20260217`
  - Task: fix failing CI lint errors on `main` introduced by daily scan + aeromexico runner changes.
  - Files: `library/aeromexico_award/runner.py`, `scripts/daily_award_scan.py`, `AGENTS.md`, `CLAUDE.md`, `codex.md`, `INPROCESS.md`
  - Status: complete (`ruff check .` clean; CI-equivalent run passed with 30 tests on Python 3.11 env)

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
