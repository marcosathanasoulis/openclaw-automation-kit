# Contributing

## Ground rules
- Keep scripts deterministic and contract-first.
- Never commit credentials or personal data.
- Declare browser domains explicitly in `manifest.json`.

## Script submission checklist
1. Add script folder under `examples/<script-name>/`
2. Include:
   - `manifest.json`
   - `schemas/input.json`
   - `schemas/output.json`
   - `runner.py`
   - `README.md`
3. Run:
   - `python -m openclaw_automation.cli validate --script-dir examples/<script-name>`
   - `pytest`
4. Open PR with test evidence.

## Provider/API adapter PR rules

If your PR adds or changes LLM/provider integrations:
1. Document required env keys in `docs/CONFIGURATION.md`.
2. Add deterministic tests (mocked provider responses where needed).
3. Keep contract compatibility (`manifest`, input/output schemas).
4. Include failure-path tests (rate limit/auth failure/timeout).

If your PR adds browser automation logic:
1. Add at least one reproducible fixture/test case.
2. Include challenge-handling behavior (`SECOND_FACTOR_REQUIRED`/`CAPTCHA_REQUIRED`) where relevant.
3. Avoid anti-bot bypass techniques.

## Security expectations
- Scope scripts to least privilege.
- Use human checkpoints for MFA/CAPTCHA.
- Do not add stealth or anti-bot bypass code.
