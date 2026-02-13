# united.award_search

Starter script for United award scans.

## Contract
- Input schema: `schemas/input.json`
- Output schema: `schemas/output.json`

## OpenClaw notes
Implement your browser actions in `runner.py`:
1. Attach to existing OpenClaw session
2. Apply award/miles + travelers + no mixed cabin filters
3. Scan date windows and extract normalized rows
4. Return canonical `matches`

## Input contract highlights
- `cabin`: `economy|business|first` (default is `economy` for broad availability scans)
- `credential_refs`: references only, e.g. `openclaw/united/username`
- Use webhook-based 2FA handoff for OTP/CAPTCHA checkpoints
