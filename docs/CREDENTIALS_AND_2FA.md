# Credentials and 2FA Security Guide

This framework can automate high-impact actions. Treat credentials and second factors as sensitive production infrastructure.

## Non-negotiable security principles
- Never store credentials in source control.
- Never hardcode secrets in scripts.
- Scope credentials per script/integration.
- Require explicit user approval for sensitive actions.
- Prefer read-only tokens where possible.
- Rotate credentials regularly.

## BYO secret-store policy
- This project does **not** provide credential import/export from Dashlane, 1Password, Chrome, or any vault.
- Users/admins provision secrets directly in their secure store.
- Scripts receive only logical references (e.g., `openclaw/united/password`) and resolve at runtime.

## Recommended credential storage by OS

### macOS (Apple Keychain)
Use Keychain as primary local secret store.

Example setup:
```bash
security add-generic-password \
  -a "$USER" \
  -s "openclaw/united/username" \
  -w "YOUR_USERNAME"

security add-generic-password \
  -a "$USER" \
  -s "openclaw/united/password" \
  -w "YOUR_PASSWORD"
```

Read at runtime:
```bash
security find-generic-password -a "$USER" -s "openclaw/united/password" -w
```

### Linux
Recommended (in order):
1. Secret Service (`gnome-keyring` / `kwallet`) via keyring-compatible clients
2. Cloud secret manager (GCP Secret Manager / AWS Secrets Manager / Vault)
3. Encrypted local file as fallback (age/sops/gpg)

If using server workloads, prefer cloud secret manager with least-privilege IAM.

### Windows
Use Windows Credential Manager or DPAPI-backed secret stores.

PowerShell example with Credential Manager module:
```powershell
New-StoredCredential -Target "openclaw/united/password" -UserName "username" -Password "secret" -Persist LocalMachine
```

## Script-side credential contract
Scripts should request credentials by logical key, never by raw value in input payloads.

Example input:
```json
{
  "credential_refs": {
    "airline_username": "openclaw/united/username",
    "airline_password": "openclaw/united/password"
  }
}
```

The runner resolves refs via a credential adapter layer.

## 2FA design (webhook-friendly)

### Baseline flow
1. Script reaches 2FA checkpoint.
2. Engine emits `SECOND_FACTOR_REQUIRED` event to configured webhook.
3. User submits code via approved channel.
4. Engine resumes run with short-lived verification token.

### Event payload example
```json
{
  "event": "SECOND_FACTOR_REQUIRED",
  "run_id": "run_123",
  "script_id": "united.award_search",
  "factor_type": "totp_or_sms",
  "expires_at": "2026-02-13T18:10:00Z",
  "resume_token": "opaque-short-lived-token"
}
```

### Resume payload example
```json
{
  "run_id": "run_123",
  "resume_token": "opaque-short-lived-token",
  "code": "123456"
}
```

## Messaging scaffolding options
- iMessage via BlueBubbles webhook bridge
- WhatsApp Cloud API webhook
- Slack interactive message / modal

Keep channel connectors out of core runtime; use webhook adapters.

## Lockdown checklist
- Use per-user/session browser profiles (isolated cookie jars).
- Encrypt stored session artifacts at rest.
- Apply audit logs for secret access and 2FA events.
- Restrict outbound domains per script manifest.
- Add allowlist/denylist for high-risk actions.
- Enforce timeout and kill-switch controls.

If this is not locked down, an automation bug can become an account takeover or financial loss event.
