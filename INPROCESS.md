# In-Process Coordination

Use this file for short-lived cross-agent coordination so parallel work does not conflict.

## Active Locks / Shared Resources

- `CDP browser`:
  - One browser automation at a time per endpoint.
  - Lock file: `/tmp/browser_cdp.lock` (managed by BrowserAgent).
  - Before long runs, note owner and target endpoint.

## Current Work

- `codex/fix-award-extraction-gap`
  - Added structured `MATCH|...` extraction path and fallback parsing.
  - Added tests in `tests/test_result_extract.py`.
  - Added validated secondary Chromium CDP endpoint on `home-mind.local:9223`.
  - Queued locked-run regression on Mac Mini:
    - script: `/tmp/openclaw-automation-kit/run_codex_regression.sh`
    - outputs: `/tmp/codex_united.json`, `/tmp/codex_sia.json`, `/tmp/codex_ana.json`
    - waits for current `/tmp/browser_cdp.lock` owner to finish.
  - Home-mind live attempt (CDP `:9223`) completed with transport issue:
    - United navigation repeatedly failed with `ERR_HTTP2_PROTOCOL_ERROR` in headless Chromium.
    - Result envelope was `mode=live`, `status=stuck`, `matches=[]`.

## Coordination Rules

- Update this file when starting/stopping long browser runs.
- Keep entries concise: `owner`, `task`, `resource`, `start_time`, `status`.
- Move durable information to `HANDOFF.md`; keep this file operational.
- After live-regression passes, run README/status refresh once (with cooldown gaps for anti-bot sites), then commit.

## Planned Regression/README Sync

- owner: `codex or parallel agent (whoever completes last live pass)`
- task: `refresh automation status + README section`
- command:
  - `python scripts/collect_automation_status.py --write-readme`
- notes:
  - run only after live tests are complete and cooldown windows are respected.
  - this is the final regression signal before release.

## Live Run Snapshot (current)

- mac-mini:
  - queued script `/tmp/openclaw-automation-kit/run_codex_regression.sh`
  - united: completed (live, non-placeholder, status=success, extraction still empty)
  - singapore: completed (live, non-placeholder, status=max_steps, extraction empty)
  - ana: currently running under lock PID `67119`
  - follow-up queued: `/tmp/run_codex_branch_live.sh` (runs latest branch code after lock clears)
- home-mind:
  - independent CDP endpoint `127.0.0.1:9223` is up
  - united/singapore/ana were run live for transport/site behavior checks
  - real Google Chrome CDP endpoint now active at `127.0.0.1:9225`
  - cooldown-enforced United live run queued via `/tmp/codex_hm_united_cooldown.sh` (75s delay before run)

## Example Entry

- owner: `codex`
- task: `SIA live search retest`
- resource: `CDP mac-mini :9222`
- start_time: `2026-02-13T06:00:00Z`
- status: `running`
