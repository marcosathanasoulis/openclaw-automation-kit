# New Automation Playbook

Best-practice path to add a new site automation script.

## 1. Scope the automation
- Define the exact user story and output JSON shape first.
- Identify required login state, MFA, and challenge points.
- Enumerate allowed domains for the script manifest.

## 2. Create script scaffold
Under `examples/<site_script>/` add:
- `manifest.json`
- `schemas/input.json`
- `schemas/output.json`
- `runner.py`
- `README.md`

Keep the automation plan minimal and explicit.

## 3. Define inputs for plain-English compatibility
For travel/search workflows, prefer:
- `from`
- `to`
- `days_ahead`
- `max_miles` or equivalent budget/cost cap
- `travelers`
- `cabin` or class tier
- `credential_refs`

This lets `run-query` map plain English consistently.

## 4. Implement runner in deterministic phases
Use predictable checkpoints:
1. setup/session attach
2. login (if needed)
3. search form fill
4. filter/sort
5. extraction
6. normalize output

Always emit `raw_observations` and `errors`.

## 5. Add challenge handling
- Detect challenge screens early.
- Capture screenshot and emit `CAPTCHA_REQUIRED`.
- Pause for human response via webhook.
- Resume with `resume_token`.

See `docs/CAPTCHA_HUMAN_LOOP.md`.

## 6. Keep credentials reference-only
- Never pass raw credentials in inputs.
- Use `credential_refs` keys and resolve at runtime.
- Validate unresolved refs and fail clearly.

See `docs/CREDENTIALS_AND_2FA.md`.

## 7. Test
Run:
```bash
python -m openclaw_automation.cli validate --script-dir examples/<site_script>
pytest
```

Add one smoke test for:
- schema validation
- runner execution
- expected required keys in result

## 8. Contribution quality bar
- No hardcoded secrets.
- No anti-bot bypass techniques.
- Clear README explaining assumptions and user checkpoints.
- Deterministic output shape.
- Logs should be useful but secret-safe.
