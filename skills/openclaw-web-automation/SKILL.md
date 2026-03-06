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

This skill itself does **not**:
- store passwords,
- resolve secret refs,
- implement browser automation logic,
- bypass CAPTCHA/anti-bot systems.

## Trusted source and version pinning

Install `openclaw-automation-kit` from the official repository:
- `https://github.com/marcosathanasoulis/openclaw-automation-kit`

Recommended:
- install from a tagged release (for example `v2026.9` or newer),
- pin to an explicit commit/tag in your internal setup docs,
- run local preflight before first use.

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
  --credential-refs-file /secure/path/credential_refs.json \
  --security-assertion-file /secure/path/security_assertion.json
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

- Security gate status:
  - Optional for local demos and no-credential checks.
  - Strongly recommended for any real credentialed/state-changing automation.
  - If not enabled, risky runs may execute without recent verified-user proof.
  - This can allow unauthorized account actions if another process/user can invoke the runner.
- Use `credential_refs` only; do not place raw passwords in command args.
- Prefer `--credential-refs-file` or `--credential-refs-env` over inline `--credential-refs` to reduce shell-history exposure.
- If inline refs are used, this launcher passes them to the backend via stdin (not argv).
- For risky/credentialed runs, configure OpenClaw security gate and pass a recent signed `security_assertion`.
- Issue an assertion after fresh TOTP verification:
  `python -m openclaw_automation.cli issue-security-assertion --user-id <you> --totp-code <code>`
- Keep human-in-the-loop for 2FA/CAPTCHA steps.
- Do not use on sites/accounts you are not authorized to access.
- Configure OpenClaw to require user confirmation for credentialed or state-changing automations.

## Data flow

- Local launcher executes local Python module: `openclaw_automation.cli`.
- Credential refs are forwarded to the local backend for resolution.
- If advanced browser flows are enabled, backend may call external model APIs (for example Anthropic) depending on your local configuration.
- iMessage notification sends only when `--send-notification` is explicitly provided.

## Dependency note

This skill is a launcher and delegates execution to `python -m openclaw_automation.cli run-query`
from your local `openclaw-automation-kit` installation.  
Optional iMessage notifications require the BlueBubbles connector module to be installed locally.

Optional environment variable:
- `OPENCLAW_AUTOMATION_ROOT`: path to trusted local `openclaw-automation-kit` checkout.

## Reliability notes

- The launcher applies short retry/backoff for transient runtime errors (for example temporary rate limits/timeouts).

## Verification checklist

```bash
python -m openclaw_automation.cli doctor --json
python -c "import openclaw_automation,sys; print('openclaw_automation import OK')"
```
