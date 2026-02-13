# Connectors (Scaffolding)

This folder contains webhook adapter scaffolding for second-factor and result delivery.

Core engine remains channel-agnostic. Adapters translate events to specific messaging services.

Planned adapters:
- `imessage_bluebubbles/`
- `whatsapp_cloud_api/`
- `slack/`

Expected challenge events from runners:
- `SECOND_FACTOR_REQUIRED`
- `CAPTCHA_REQUIRED`

Each connector should:
1. deliver challenge text + screenshot URL to user
2. parse user response
3. call resume endpoint with `run_id`, `step_id`, `resume_token`, and `solution`
