# Automation Promotion Policy (`examples` -> `library`)

Use this policy to decide when an automation is ready to move from starter/demo quality to approved reusable library quality.

## Lifecycle

1. `examples/<name>`: starter and exploratory scripts.
2. `library/<name>`: approved, reusable scripts expected to be stable for users.

## Promotion gate (all required)

- Contract complete:
  - `manifest.json`
  - `schemas/input.json`
  - `schemas/output.json`
  - `runner.py`
  - script `README.md` with clear run instructions
- Safety complete:
  - no raw credentials anywhere
  - `credential_refs` used when auth is required
  - 2FA/CAPTCHA human-loop behavior documented
  - no anti-bot bypass logic
- Test complete:
  - `ruff check .`
  - `pytest -q`
  - `python -m openclaw_automation.cli validate --script-dir <path>`
  - no-login smoke still passing (`./scripts/e2e_no_login_smoke.sh`)
  - one script-specific smoke run attached in PR
- Failure handling complete:
  - explicit handling for timeout/challenge/error
  - output shape remains schema-valid on failure

## Required PR evidence for promotion

- Before/after script path
- validation output
- smoke command + JSON result excerpt
- known limitations and expected human checkpoints

## Demotion rule

If a `library/` automation becomes unstable or loses reproducibility, move it back to `examples/` until fixed.
