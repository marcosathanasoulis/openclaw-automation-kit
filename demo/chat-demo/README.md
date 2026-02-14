# OpenClaw Local Chat Demo

Local browser-automation demo UI for the OpenClaw Automation Kit.

## What this does

- Serves a chat-style web UI on `http://127.0.0.1:8090`
- Accepts plain-English automation prompts
- Calls `python -m openclaw_automation.cli run-query --query "..."`
- Shows a human-friendly summary plus raw JSON output
- Includes canned no-login demos:
  - `Run headlines demo`
  - `Run text watch demo`
  - `Run captcha demo`
  - `Run 2FA demo`

## Run with Docker

From repo root:

```bash
./demo/chat-demo/run_local_docker.sh
```

Then open:

`http://127.0.0.1:8090`

## Manual commands

```bash
docker build -t openclaw-chat-demo:local -f demo/chat-demo/Dockerfile .
docker rm -f openclaw-chat-demo || true
docker run -d --name openclaw-chat-demo -p 8090:8080 openclaw-chat-demo:local
```

## Quick API smoke test

```bash
curl -sS http://127.0.0.1:8090/healthz
curl -sS -X POST http://127.0.0.1:8090/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Check yahoo.com and tell me the top headlines"}' | python -m json.tool
```

## Human-loop CAPTCHA demo (safe mock)

In chat, send:

`Run captcha demo`

The demo returns a generated challenge image URL and prompt:

`solve <challenge_id> n,n,n`

Example:

`solve a1b2c3d4e5 2,5,9`

This demonstrates pause/resume with human intervention using a sandbox challenge (no real third-party CAPTCHA service, no personal account access).

## Simulated 2FA demo (safe mock)

In chat, send:

`Run 2FA demo`

The demo returns a simulated inbox URL and flow id. Open the inbox URL to read the one-time code, then reply:

`otp <flow_id> <6-digit-code>`

This demonstrates external code delivery + resume without using any personal account.
