# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.
  - Current owner: none.
  - Status: lock currently clear on `marcoss-mac-mini.local:9222` after the latest United probes; stale lock cleanup verified.

## Current Work

- `codex/award-search-reliability`
  - Task: diagnose why airline award sessions lose cookies / trigger frequent 2FA, fix the active BrowserAgent/runtime path, and move United toward the true award-search flow.
  - Files: `INPROCESS.md`, `src/openclaw_automation/browser_agent_adapter.py`, `src/openclaw_automation/adaptive.py`, `src/openclaw_automation/engine.py`, `library/united_award/runner.py`, `tests/test_award_runners.py`, `tests/test_browser_agent_adapter.py`, `tests/test_public_page_example.py`, `scripts/e2e_no_login_smoke.sh`
  - Status: IN PROGRESS
  - Coordination notes:
    - No CDP endpoint currently claimed.
    - Validated locally:
      - `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_award_runners.py tests/test_browser_agent_adapter.py` (8 passed)
      - `python3 -m py_compile library/united_award/runner.py src/openclaw_automation/browser_agent_adapter.py tests/test_award_runners.py tests/test_browser_agent_adapter.py`
    - New fixes landed:
      - `src/openclaw_automation/browser_agent_adapter.py`: `OPENCLAW_BROWSER_AGENT_PATH` now wins over repo-local `src/browser_agent.py`, so runtime finally imports `/Users/marcos/athanasoulis-ai-assistant/src/browser/browser_agent.py`.
      - `library/united_award/runner.py`: start BrowserAgent on the cash-results URL instead of the homepage, and use `days_ahead` consistently for the goal and initial URL.
      - `tests/test_browser_agent_adapter.py`: regression for explicit module-path precedence.
      - `tests/test_award_runners.py`: regression that United starts on the cash-results URL.
    - Safe to proceed with non-CDP repo changes only; do not touch `library/united_award/*` while `codex/united-run-stability` is active there.
    - `library/united_award/*` was clean in the local worktree when the above minimal fix landed; no concurrent live process was active on `marcoss-mac-mini.local:9222` during those edits.
    - Latest live findings from `mac-mini` `9222`:
      - United cash-results rerun now completes end-to-end with the correct assistant BrowserAgent, CDP lock, screenshots, and run trace.
      - That corrected cash-results path still returns only USD fares, because it is following United's Money/Money+Miles product rather than the true award-search path.
      - Deterministic homepage submit with award checkbox checked creates a different URL: `...at=1...tqp=A`, which appears to be the true award path.
      - The `at=1` path currently shows a sign-in modal over skeleton award cards. Keychain credential lookup works there, but the remembered-account shortcut returned `The account information entered is invalid`, so the next likely fix is a deterministic `Switch accounts` or homepage-submit flow.
      - Delta `SFO->{LHR,CDG,AMS,FRA,MAD}`, business, 2 travelers, next 30 days: runner hung idle and was terminated
      - JetBlue `SFO->{NRT,HND}`, business, 2 travelers, next 30 days: `BrowserAgent status: error`, `steps: 0`, empty matches
      - ANA `SFO->{HND,NRT}`, business, 2 travelers, next 30 days: `real_data: false`, BrowserAgent-only fallback, empty matches
      - AeroMexico `SFO->{PVR,CUN}`, economy, 2 travelers, next 30 days: `BrowserAgent status: error`, `steps: 1`, empty matches
      - Singapore `SFO->BKK`, business, 2 travelers, next 30 days: runner hung idle and was terminated
    - Interpretation:
      - empty match lists are currently not trustworthy unless the runner explicitly reports a completed live path without BrowserAgent errors
      - failure mode is shared across airlines and points to the active BrowserAgent/runtime stack, not just one script
    - Current local work:
      - `src/openclaw_automation/browser_agent_adapter.py`: wire `OPENCLAW_BROWSER_SEND_UPDATES` into `BrowserAgent(...)`
      - `tests/test_public_page_example.py`: align headline-routing expectation with current NL router so CI passes
      - `src/openclaw_automation/adaptive.py` / `engine.py`: fail closed when BrowserAgent returns `status=error|stuck|max_steps|interrupted` so assistant mode stops treating those as real empty availability
    - Validation completed:
      - `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_browser_agent_adapter.py tests/test_public_page_example.py tests/test_award_runners.py tests/test_engine_envelope.py` (15 passed)
      - direct normalization check confirms BrowserAgent `status=error` now clears matches and marks result non-real
      - `bash scripts/e2e_no_login_smoke.sh` now passes after updating the public-query expectation and restoring backward compatibility for mock BrowserAgent implementations without `send_updates` / `status`
      - Live mac-mini validation after runtime deploy:
        - JetBlue `SFO -> NRT`, 2 travelers, business, next 30 days now progresses through real site navigation and login flow instead of failing immediately with `status=error`, `steps=0`
        - Current blocker is login-form semantics: the agent repeatedly tried to `type` into literal selector labels (`input[name=\"username\"]`, `#username`) and timed out instead of reliably targeting the actual field
        - Browser process was released after the probe; no CDP lock file remained

- `codex/secure-skill-sync`
  - Task: fetch secure, helpful OpenClaw skill updates from `origin/main` without regressing web-query routing behavior.
  - Files: `INPROCESS.md`, `skills/openclaw-award-search/*`, `skills/openclaw-web-automation-basic/*`, `skills/openclaw-web-automation/SKILL.md`, `skills/openclaw-web-automation/scripts/run_query.py`
  - Status: COMPLETE
  - Validation target:
    - confirm no secrets in imported skill files
    - `PYTHONPATH=src pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py`
  - Coordination notes:
    - no CDP lock required (skills/docs sync only)
  - Validation results:
    - Security scan: no embedded secrets/tokens/keys detected in synced skill files (only documented credential-ref placeholders).
    - Tests passed: `PYTHONPATH=src pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py` (8 passed).
    - Live smoke:
      - `home-mind`: `skills/openclaw-web-automation/scripts/run_query.py --query "Find the latest AI policy headlines today"` returned `script_id=web.web_search_brief`, `ok=true`.
      - `mac-mini`: `skills/openclaw-web-automation/scripts/run_query.py --query "Fetch the latest headlines from Google News"` returned `script_id=web.site_headlines`, `ok=true`.
  - Deployment:
    - Synced updated skill files to both `home-mind` and `marcoss-mac-mini.local` at `~/openclaw-automation-kit/skills/...`.

- `codex/web-query-generic-routing`
  - Task: route generic web-search intents (no URL) to `library/web_search_brief` instead of Yahoo public-page fallback.
  - Files: `INPROCESS.md`, `src/openclaw_automation/nl.py`, `tests/test_nl_web_query_routing.py`
  - Status: COMPLETE
  - Validation target:
    - `PYTHONPATH=src pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py`
    - `python -m openclaw_automation.cli run-query --query "Find the latest AI policy headlines today"`
  - Coordination notes:
    - Live verification claimed/released `mac-mini-openclaw-cdp`.
  - Validation results:
    - Tests passed: `PYTHONPATH=src pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py` (8 passed).
    - Local run-query now routes generic intent to `web.web_search_brief` with Reuters/TechCrunch/Google News results.
    - Deployed updated `src/openclaw_automation/nl.py` to `marcoss-mac-mini.local` and `home-mind.local`.
    - Live mac-mini verification:
      - Query: "Find the latest AI policy headlines today"
      - `script_id: web.web_search_brief`
      - Top results included Reuters + TechCrunch (no Yahoo fallback).

- `codex/openclaw-web-query-routing`
  - Task: route Google News / restaurant / hotel NL prompts to dedicated web scripts instead of default Yahoo page check fallback.
  - Files: `INPROCESS.md`, `src/openclaw_automation/nl.py`, `library/web_search_brief/*`, `tests/test_nl_web_query_routing.py`, `tests/test_library_web_search_brief.py`
  - Status: COMPLETE
  - Validation target:
    - `pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py`
    - `python -m openclaw_automation.cli run-query --query "Fetch the latest headlines from Google News"`
    - `python -m openclaw_automation.cli run-query --query "Find the best French restaurant in Marin County, California"`
    - `python -m openclaw_automation.cli run-query --query "Find the best hotel prices for March 12-15 in Manhattan for a one-bedroom suite"`
  - Validation results:
    - Local tests passed: `PYTHONPATH=src pytest -q tests/test_nl_web_query_routing.py tests/test_library_web_search_brief.py tests/test_nl_workspace_bridge.py tests/test_library_public_scripts.py` (13 passed).
    - Local run-query checks route correctly:
      - Google News -> `library/site_headlines`
      - Restaurant/Hotel -> `library/web_search_brief`
    - Deployed updated files to `marcoss-mac-mini.local` and `home-mind.local`.
    - Live mac-mini run-query checks (under `mac-mini-openclaw-cdp` lock) returned:
      - Google News headlines summary from `news.google.com`.
      - Marin French restaurant ranked links (Yelp/Tripadvisor/Marin Magazine).
      - Manhattan hotel ranked links with detected best visible price hint (`$77` from Skyscanner in snippet data).
  - Coordination notes:
    - Claimed and released `mac-mini-openclaw-cdp` lock during live verification.

- `codex/united-run-stability`
  - Task: diagnose and fix United award run failure (`united_award_monthly.py`) seen from assistant mode tests.
  - Files: `INPROCESS.md`, `library/united_award/*`, `tests/*`
  - Status: IN PROGRESS
  - Validation target:
    - `python -m openclaw_automation.cli run-query --query "Search United business SFO to NRT this week for 2 travelers"`
    - `pytest -q` targeted United parser/smoke tests

- `codex/cdp-concurrency-policy`
  - Task: codify strict CDP multi-agent locking rules across assistant and OpenClaw repos so same-endpoint tab/session races are blocked.
  - Files: `INPROCESS.md`, `AGENTS.md`
  - Status: COMPLETE
  - Coordination notes:
    - No shared CDP resource currently claimed by this task (docs-only pass).
    - Policy target: one agent per endpoint, parallel only across distinct endpoints/ports with separate browser profiles.
  - Handoff:
    - Commit: `a1dae80` (`docs(agents): codify cdp endpoint concurrency policy`)
    - Branch: `codex/cdp-concurrency-policy`

- `codex/award-manifest-gap-fix`
  - Task: restore missing manifest/schema files for `jetblue_award` and `aeromexico_award` so `run-query` works for all target airlines.
  - Files: `INPROCESS.md`, `library/jetblue_award/manifest.json`, `library/jetblue_award/schemas/*`, `library/aeromexico_award/manifest.json`, `library/aeromexico_award/schemas/*`
  - Status: COMPLETE
  - Validation target:
    - `python -m openclaw_automation.cli validate --script-dir library/jetblue_award`
    - `python -m openclaw_automation.cli validate --script-dir library/aeromexico_award`
    - `python -m openclaw_automation.cli run-query --query "...JetBlue..."`
    - `python -m openclaw_automation.cli run-query --query "...AeroMexico..."`

- `codex/imessage-allowlist-identity` (security hardening pass)
  - Task: remove embedded iMessage token/recipient from automation scripts and require env-based secure config.
  - Files: `INPROCESS.md`, `scripts/daily_award_scan.py`, `.env.example`, `docs/CONFIGURATION.md`
  - Status: COMPLETE
  - Deployment:
    - Applied to `marcoss-mac-mini.local` and `home-mind.local`.
    - Added required env keys in `~/openclaw-automation-kit/.env`:
      - `OPENCLAW_IMESSAGE_SEND_URL`
      - `OPENCLAW_IMESSAGE_BOT_TOKEN`
      - `OPENCLAW_IMESSAGE_DEFAULT_RECIPIENT`
      - `OPENCLAW_IMESSAGE_ALLOWED_RECIPIENTS`
    - Dry-run validation on mac mini:
      - `scripts/daily_award_scan.py --dry-run --only united`
  - Validation:
    - `python3 -m py_compile scripts/daily_award_scan.py`
    - `pytest -q tests/test_imessage_guardrails.py` (2 passed)

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
