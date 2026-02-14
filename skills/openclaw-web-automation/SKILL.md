---
name: openclaw-web-automation
description: Automates web interactions for public checks and authenticated workflows, with credential references, human-mediated CAPTCHA handling, optional 2FA orchestration, and optional iMessage task-completion notifications.
---

# OpenClaw Web Automation (Unified)

This skill supports both:
- Basic mode: public-site checks with no credentials
- Advanced mode: authenticated flows with `credential_refs` and optional iMessage notifications

Setup metadata:
- `setup.json` in this folder lists prerequisites and verification steps.

## Trust boundary

This skill is a launcher. It delegates execution to your local
`openclaw_automation.cli run-query` implementation from `openclaw-automation-kit`.
Optional iMessage notifications delegate to a local BlueBubbles connector module if installed.

## Examples

Basic:

```bash
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Check yahoo.com and tell me the top headlines"
```

Preflight:

```bash
python -m openclaw_automation.cli doctor --json
```

Advanced (credentialed):

```bash
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Search United award travel economy from SFO to AMS in next 30 days under 120k miles" \
  --credential-refs-file /secure/path/credential_refs.json
```

Where `/secure/path/credential_refs.json` contains:

```json
{
  "airline_username": "openclaw/united/username",
  "airline_password": "openclaw/united/password"
}
```

Optional iMessage notify (dry run by default):

```bash
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Search ANA economy from SFO to HND in next 30 days under 120k" \
  --credential-refs '{"airline_username":"openclaw/ana/username","airline_password":"openclaw/ana/password"}' \
  --notify-imessage "+1XXXXXXXXXX"
```

Actually send notification:

```bash
python skills/openclaw-web-automation/scripts/run_query.py \
  --query "Search ANA economy from SFO to HND in next 30 days under 120k" \
  --credential-refs '{"airline_username":"openclaw/ana/username","airline_password":"openclaw/ana/password"}' \
  --notify-imessage "+1XXXXXXXXXX" \
  --send-notification
```

## Safety

- Use `credential_refs` only; do not place raw passwords in command args.
- Prefer `--credential-refs-file` or `--credential-refs-env` over inline `--credential-refs` to reduce shell-history exposure.
- If inline refs are used, this launcher passes them to the backend via stdin (not argv).
- Keep human-in-the-loop for 2FA/CAPTCHA steps.
- Do not use on sites/accounts you are not authorized to access.

## Dependency note

This skill is a launcher and delegates execution to `python -m openclaw_automation.cli run-query`
from your local `openclaw-automation-kit` installation.  
Optional iMessage notifications require the BlueBubbles connector module to be installed locally.

Optional environment variable:
- `OPENCLAW_AUTOMATION_ROOT`: path to trusted local `openclaw-automation-kit` checkout.

## Reliability notes

- The launcher applies short retry/backoff for transient runtime errors (for example temporary rate limits/timeouts).
