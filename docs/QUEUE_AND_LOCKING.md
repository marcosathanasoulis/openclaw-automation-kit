# Queue and Locking Model

Automation reliability depends on scheduling discipline.  
Do not rely on ad-hoc parallel tabs in a shared browser profile.

## Default policy
- Queue all runs.
- `max_concurrent_runs = 1` by default.
- Only raise concurrency for scripts proven isolation-safe.

## Execution modes

Use one of these modes per script:

1. `exclusive`
- one run at a time globally
- ideal for login-heavy and MFA-sensitive workflows

2. `profile_isolated`
- concurrent runs allowed only when browser profiles are isolated
- lock key includes profile id

3. `stateless`
- parallel runs allowed
- no shared browser session state

## Resource locks

Lock keys should be deterministic and explicit, for example:
- `browser_profile:default`
- `site:united.com`
- `connector:imessage`

If a required lock is held:
- keep run queued
- retry based on backoff policy

## BrowserAgent CDP file lock (implemented)

For BrowserAgent-based runs, this repo now uses a file lock to serialize access
to shared Chrome CDP sessions:
- default lock file: `/tmp/browser_cdp.lock`
- stale PID detection and cleanup
- bounded wait with timeout/retry controls

Config:
- `OPENCLAW_CDP_LOCK_FILE`
- `OPENCLAW_CDP_LOCK_TIMEOUT`
- `OPENCLAW_CDP_LOCK_RETRY_SECONDS`

## Queue behavior

- FIFO with optional priority classes
- retry on transient failures
- cooldown/rate-limit support per site
- idempotent run IDs for replay safety

## Human-loop interactions

When a run pauses for challenge handling (`SECOND_FACTOR_REQUIRED`/`CAPTCHA_REQUIRED`):
- keep ownership on the same run id
- prevent duplicate pending challenge states
- expire stale challenges with clear run status

## Why this matters

Without queue + lock policy, concurrent runs can:
- overwrite fields in shared tabs
- cross-wire login/session state
- send wrong challenge prompts to users
- produce incorrect extraction output
