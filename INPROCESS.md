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

## Coordination Rules

- Update this file when starting/stopping long browser runs.
- Keep entries concise: `owner`, `task`, `resource`, `start_time`, `status`.
- Move durable information to `HANDOFF.md`; keep this file operational.

## Example Entry

- owner: `codex`
- task: `SIA live search retest`
- resource: `CDP mac-mini :9222`
- start_time: `2026-02-13T06:00:00Z`
- status: `running`
