# github.signin_check

Minimal onboarding example for messaging-driven 2FA.

What it demonstrates:
- credential references (`credential_refs`) instead of raw passwords
- event payload emitted when human input is required
- connector handoff shape for iMessage/WhatsApp/Slack

This runner is intentionally a scaffold:
- replace with real OpenClaw steps for GitHub login
- keep the `SECOND_FACTOR_REQUIRED` event contract
- resume flow through your API (`POST /runs/{id}/resume`)

