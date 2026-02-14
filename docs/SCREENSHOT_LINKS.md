# Screenshot Links for Human-Loop Challenges

If an automation needs a human to solve CAPTCHA/2FA from a screenshot, the user needs a link they can open in chat.

## Lightweight local option

Serve your artifact directory:

```bash
python scripts/serve_artifacts.py --dir browser_runs --port 8765
```

This gives local links like:

`http://127.0.0.1:8765/2026-02-14_123000_some_run/screenshots/step_012.png`

## Remote access option

If the user is not on the same machine/network, expose that local port with your preferred tunnel/reverse proxy.

## Security notes

- Only serve artifact folders (not your home directory).
- Use short-lived/tight access controls for any public tunnel.
- Do not expose traces containing secrets or personal data.
