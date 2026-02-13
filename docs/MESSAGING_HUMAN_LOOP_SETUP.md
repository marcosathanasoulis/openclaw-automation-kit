# Messaging + Human-Loop Setup

This is the minimum production pattern for login challenges:
- user asks for automation run
- script starts browser flow
- script hits 2FA/CAPTCHA checkpoint
- script sends challenge event to messaging connector
- user replies with code or tile selection
- script resumes and completes

## 1) Required components

1. Automation runner (this repo)
2. Messaging connector (iMessage/WhatsApp/Slack)
3. Webhook endpoint that receives challenge events
4. Resume endpoint (`POST /runs/{id}/resume`) to continue blocked runs

## 2) Challenge event payload

```json
{
  "event": "CAPTCHA_REQUIRED",
  "run_id": "run_123",
  "step_id": "captcha_1",
  "script_id": "united.award_search",
  "instructions": "Select all tiles with airplanes",
  "challenge_type": "tile_grid",
  "grid_size": "3x4",
  "screenshot_url": "https://signed-url/challenge.png",
  "resume_token": "opaque-short-lived-token",
  "expires_at": "2026-02-14T08:10:00Z"
}
```

For OTP:

```json
{
  "event": "SECOND_FACTOR_REQUIRED",
  "run_id": "run_456",
  "step_id": "otp_1",
  "script_id": "github.signin_check",
  "factor_type": "totp_or_sms",
  "instructions": "Enter the 6-digit verification code",
  "resume_token": "opaque-short-lived-token"
}
```

## 3) User reply payload

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

For OTP:

```json
{
  "run_id": "run_456",
  "step_id": "otp_1",
  "resume_token": "opaque-short-lived-token",
  "solution": {
    "type": "otp_code",
    "value": "123456"
  }
}
```

## 4) iMessage path (BlueBubbles)

1. Receive challenge event in your bridge service.
2. Send `instructions + screenshot_url` via BlueBubbles.
3. Parse user reply from iMessage thread.
4. Call your resume endpoint with parsed solution payload.

Use starter connector:
- `connectors/imessage_bluebubbles/webhook_example.py`

## 5) WhatsApp path

1. Receive challenge event in your bridge service.
2. Send image + text prompt through WhatsApp Cloud API.
3. Parse inbound response.
4. Call resume endpoint.

Use starter connector:
- `connectors/whatsapp_cloud_api/webhook_example.py`

## 6) Security requirements

- Resume tokens must be short-lived and one-time-use.
- Validate sender identity before accepting challenge responses.
- Keep challenge screenshots signed and short-lived.
- Never log OTP codes or credential values.

