## Summary

## Change type
- [ ] New automation in `examples/`
- [ ] Promotion from `examples/` to `library/`
- [ ] Update to existing `library/` automation
- [ ] Core engine/framework change

## Automation contract
- [ ] `manifest.json` added/updated
- [ ] `schemas/input.json` added/updated
- [ ] `schemas/output.json` added/updated
- [ ] `runner.py` added/updated
- [ ] `README.md` added/updated

## Security + safety
- [ ] No raw credentials in code, tests, docs, or examples
- [ ] Uses `credential_refs` only (if auth is needed)
- [ ] Human-loop behavior documented for 2FA/CAPTCHA (if relevant)
- [ ] No anti-bot bypass techniques introduced
- [ ] Domain scope in manifest is least-privilege

## Test evidence
- [ ] `ruff check .`
- [ ] `pytest -q`
- [ ] `python -m openclaw_automation.cli validate --script-dir <path>`
- [ ] `./scripts/e2e_no_login_smoke.sh` (or explain why not applicable)
- [ ] Smoke output attached (command + JSON excerpt)

## Promotion checklist (required when moving into `library/`)
- [ ] Stable output shape verified across repeated runs
- [ ] At least one failure-path test (timeout/challenge/error) added
- [ ] Runbook notes included in script README
- [ ] Reviewer can reproduce with documented commands

## Notes for reviewers
