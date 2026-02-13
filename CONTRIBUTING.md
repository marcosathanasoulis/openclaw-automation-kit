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

## Security expectations
- Scope scripts to least privilege.
- Use human checkpoints for MFA/CAPTCHA.
- Do not add stealth or anti-bot bypass code.
