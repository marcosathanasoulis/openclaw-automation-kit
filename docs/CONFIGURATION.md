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

## Optional BrowserAgent integration settings

Use these when integrating an external `BrowserAgent` implementation (for example, from your assistant codebase).

### `OPENCLAW_USE_BROWSER_AGENT`
- Set to `true`/`1` to enable BrowserAgent execution path in award scripts.

### `OPENCLAW_BROWSER_AGENT_MODULE`
- Python module name to import (default: `browser_agent`).

### `OPENCLAW_BROWSER_AGENT_PATH`
- Filesystem path to append to `sys.path` before import.
- Example: `/Users/you/athanasoulis-ai-assistant/src/browser`
- Security note: this is dynamic module loading. Treat this path as trusted code only.

### `OPENCLAW_CDP_URL`
- Chrome DevTools endpoint used by BrowserAgent.
- Default: `http://127.0.0.1:9222`

### `OPENCLAW_CDP_LOCK_FILE`
- File lock path used to serialize CDP BrowserAgent runs.
- Default: `~/.openclaw/browser_cdp.lock`

### `OPENCLAW_CDP_LOCK_TIMEOUT`
- Max seconds to wait for CDP lock before failing.
- Default: `600`

### `OPENCLAW_CDP_LOCK_RETRY_SECONDS`
- Retry interval while waiting for lock.
- Default: `5`

## Using the Mock BrowserAgent for Testing

For development and testing purposes, a mock `BrowserAgent` is provided in the `_test_browser_agent/browser_agent.py` file. This allows you to test automations that use the `run_browser_agent_goal` function without needing a live browser instance or an external AI model.

To use the mock agent:

1.  Ensure the `_test_browser_agent` directory is in your Python path or set `OPENCLAW_BROWSER_AGENT_PATH`.
2.  Set the following environment variables:
    *   `OPENCLAW_USE_BROWSER_AGENT=true`
    *   `OPENCLAW_BROWSER_AGENT_MODULE=_test_browser_agent.browser_agent`
    *   `OPENCLAW_BROWSER_AGENT_PATH=/path/to/your/openclaw-automation-kit` (Replace with the actual root path of the cloned repository)

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
