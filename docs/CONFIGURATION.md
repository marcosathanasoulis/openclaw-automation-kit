# Configuration and API Keys

This project uses a bring-your-own-key model.

Never commit keys to git. Use local environment variables, OS keychain, or cloud secret managers.

## Required for browser-agent workflows

### `ANTHROPIC_API_KEY`
- Used for Claude-based browser reasoning/vision in current recommended flows.
- Reason: today this has been the most reliable approach in our browser automation stack.

## Optional provider keys (for community adapters)

### `OPENAI_API_KEY`
- For contributors adding OpenAI-based reasoning adapters.

### `GOOGLE_API_KEY`
- For contributors adding Gemini-based reasoning adapters.

## Optional OpenClaw runtime settings

### `OPENCLAW_BASE_URL`
- If your OpenClaw endpoint is not default local/CLI behavior.

### `OPENCLAW_API_KEY`
- If your OpenClaw deployment requires API auth.

## Optional messaging connector keys

### BlueBubbles (iMessage bridge)
- `BLUEBUBBLES_WEBHOOK_URL`
- `BLUEBUBBLES_TOKEN`

### WhatsApp Cloud API
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_ACCESS_TOKEN`

## Recommended setup flow

1. Copy `.env.example` to `.env` locally.
2. Set only the keys you actually use.
3. Keep credentials in secure stores and pass only `credential_refs` to scripts.
4. Use messaging connectors for 2FA/CAPTCHA handoff.

