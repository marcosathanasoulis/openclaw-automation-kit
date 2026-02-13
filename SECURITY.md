# Security Policy

## Scope

This project includes browser automation patterns that may operate with user credentials and second-factor checkpoints.
Treat deployments as high-risk systems unless locked down.

## Reporting a vulnerability

Please do not open public issues for sensitive security findings.

Report privately via:
- GitHub Security Advisories (preferred), or
- direct maintainer contact through repository owner profile.

Include:
- affected component/file
- impact summary
- minimal reproduction steps
- recommended mitigation (if known)

## Immediate operator guidance

- Rotate any exposed credentials immediately.
- Revoke compromised tokens/sessions.
- Disable automation runs until root cause is contained.
- Review audit logs for misuse.

## Supported hardening expectations

- No secrets in source control
- Credential refs only in payloads
- Human-loop for 2FA/CAPTCHA on sensitive flows
- Least-privilege secret-store access
- Action-level allowlists for high-risk operations
