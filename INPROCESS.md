# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.

## Current Work

- `codex/google-workspace-bridge`
  - Task: route calendar/email queries to Google Workspace bridge using existing refresh tokens on Mac Mini/home-mind.
  - Files: `INPROCESS.md`, `src/openclaw_automation/nl.py`, `examples/google_workspace_brief/*`, `.env.example`, `docs/CONFIGURATION.md`, `tests/test_nl_workspace_bridge.py`
  - Status: COMPLETE
  - Validation:
    - `pytest -q tests/test_imessage_guardrails.py tests/test_nl_workspace_bridge.py` (7 passed)
    - `python -m openclaw_automation.cli validate --script-dir examples/google_workspace_brief`
    - `python -m openclaw_automation.cli run-query --query \"Tell me my meetings on Monday\"` routes to `examples/google_workspace_brief` and fails closed when token file is missing locally.
  - Security:
    - Read-only Gmail/Calendar API usage only.
    - Enforced Google account allowlist (`OPENCLAW_GOOGLE_ALLOWED_ACCOUNTS`).
  - Follow-up:
    - Default behavior now checks all allowlisted accounts when `account_email` is not provided.
    - Meetings/emails now include `account_email` per result row.
    - Live validation on `home-mind` succeeded for:
      - `what meetings do I have monday`
      - `when was the last time deryk emailed me`

- `codex/imessage-allowlist-identity`
  - Task: enforce iMessage recipient allowlist and add explicit OpenClaw sender tag for parallel agent separation.
  - Files: `INPROCESS.md`, `connectors/imessage_bluebubbles/webhook_example.py`, `skills/openclaw-web-automation/scripts/run_query.py`, `docs/CONFIGURATION.md`, `.env.example`
  - Status: COMPLETE
  - Validation: `pytest -q tests/test_imessage_guardrails.py` (2 passed)
  - Note: Restrict outbound to Marcos only (`+14152268266`, `marcos@athanasoulis.net`) unless explicitly expanded.

- **claude/daily-award-scan** (Claude Opus agent, Feb 16-17)
  - Task: Daily automated award search for June 2026 across 6 airlines
  - Commits on main: 2ac377c (runners), e1527d1 (daily scan), 348652d (fix), f7e8f9f (lint)
  - Status: IN PROGRESS — overnight scan running on Mac Mini CDP (ANA, SIA, JetBlue, AeroMexico, Delta)
  - Launchd: `com.athanasoulis.daily-award-search` scheduled 6 AM daily on Mac Mini
  - Note: PR #18 (codex lint fix) closed — superseded by f7e8f9f already on main

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
