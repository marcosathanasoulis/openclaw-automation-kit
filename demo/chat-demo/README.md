# OpenClaw Local Chat Demo

Local browser-automation demo UI for the OpenClaw Automation Kit.

## What this does

- Serves a chat-style web UI on `http://127.0.0.1:8090`
- Accepts plain-English automation prompts
- Calls `python -m openclaw_automation.cli run-query --query "..."`
- Shows a human-friendly summary plus raw JSON output

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
