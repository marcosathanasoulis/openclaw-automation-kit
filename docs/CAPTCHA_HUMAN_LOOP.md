# CAPTCHA Human-Loop Architecture

Use a human checkpoint for CAPTCHA and other anti-bot challenges.

## Goals
- Keep automation reliable without bypass techniques.
- Keep user control for sensitive or challenge-gated actions.
- Keep channel delivery pluggable (iMessage/WhatsApp/Slack/etc.).

## Flow
1. Script detects challenge state (`CAPTCHA_REQUIRED`).
2. Script captures:
   - screenshot
   - challenge type (tiles, text, OTP, etc.)
   - prompt text (if available)
   - run id + step id
3. Engine emits webhook event to a connector.
4. Connector sends a human-readable message with screenshot URL.
5. User replies with solution payload.
6. Connector calls resume endpoint with `run_id`, `resume_token`, and `solution`.
7. Engine validates token, resumes runner, and continues.

## Event shape (example)
```json
{
  "event": "CAPTCHA_REQUIRED",
  "run_id": "run_123",
  "step_id": "captcha_1",
  "script_id": "united.award_search",
  "challenge_type": "tile_grid",
  "instructions": "Select all tiles with buses",
  "grid_size": "3x4",
  "screenshot_url": "https://signed.example/challenge.png",
  "resume_token": "opaque-short-lived-token",
  "expires_at": "2026-02-14T08:10:00Z"
}
```

## User reply shape (example)
```json
{
  "run_id": "run_123",
  "step_id": "captcha_1",
  "resume_token": "opaque-short-lived-token",
  "solution": {
    "type": "tile_indexes",
    "value": [5, 9]
  }
}
```

## Connector guidance
- iMessage/BlueBubbles: send screenshot + concise instruction text.
- WhatsApp Cloud API: send image + quick-reply template.
- Slack: use interactive message buttons or modal.

## Security controls
- `resume_token` must be short-lived and one-time-use.
- Log challenge lifecycle events, never raw credentials.
- Bind response to original run + user identity.
- Reject stale responses after expiry.
- Keep screenshot URLs signed and short-lived.

## What not to do
- Do not add stealth CAPTCHA bypass logic.
- Do not auto-solve CAPTCHAs with hidden third-party services by default.
- Do not continue automation after unresolved challenge timeout.

