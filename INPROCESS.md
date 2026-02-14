# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.

## Current Work

- `codex/fix-ci-lint-feb14`
  - Task: diagnose and fix current CI failure on `feat/skill-manifests-and-tests`.
  - Files: `tests/test_adaptive.py`
  - Status: complete (AeroMexico validation tests now match cash-pricing validator logic)

- `codex/fix-lint-united-runner`
  - Task: fix CI lint failure on `library/united_award/runner.py` in `cc/fix-health-check-direct-mode` lineage.
  - Files: `library/united_award/runner.py`
  - Status: complete (removed two unused local assignments flagged by Ruff F841)

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

- `codex/fix-lint-united-runner`
  - Task: fix CI lint failure on `library/united_award/runner.py` in `cc/fix-health-check-direct-mode` lineage.
  - Files: `library/united_award/runner.py`
  - Status: in progress
