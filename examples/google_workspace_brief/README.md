# google_workspace_brief

Fetches Google Calendar meetings and/or Gmail summaries using existing OAuth token files.

## Security

- Read-only scopes only (`calendar.readonly`, `gmail.readonly`)
- Uses existing refresh tokens; does not print secret values
- Fails closed when token/client-secret files are missing

## Required local config

Set these on the machine where tokens live (Mac mini/home-mind):

```bash
export OPENCLAW_GOOGLE_CONNECTOR_ROOT=/path/to/athanasoulis-ai-assistant
export OPENCLAW_GOOGLE_ACCOUNT=marcos@athanasoulis.net
export OPENCLAW_GOOGLE_CLIENT_SECRET_PATH=$OPENCLAW_GOOGLE_CONNECTOR_ROOT/credentials/google/client_secret.json
export OPENCLAW_GOOGLE_TOKEN_DIR=$OPENCLAW_GOOGLE_CONNECTOR_ROOT/credentials/google/tokens
```

## Example runs

Meetings for a date:

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/google_workspace_brief \
  --input '{"task":"meetings","date":"2026-03-02","account_email":"marcos@athanasoulis.net"}'
```

Latest emails:

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/google_workspace_brief \
  --input '{"task":"emails","account_email":"marcos@athanasoulis.net","max_results":10}'
```
