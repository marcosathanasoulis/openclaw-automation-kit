# Regression Tiers

This project uses three regression tiers. Treat them as release gates.

## Critical

Security and "must never happen" behavior.

- Risky/credentialed automation is blocked when user verification assertion is missing/invalid/expired.
- Assertion must be tied to expected user identity and signed.
- TOTP verification path must work.

Run:

```bash
./scripts/regression/critical/security_gate.sh
```

## Medium

Core workflows that should generally work.

- Human-loop 2FA event shape remains stable.
- Engine envelope remains valid.

Run:

```bash
./scripts/regression/medium/core_flows.sh
```

## Low

Broader smoke and convenience checks.

- Public no-login examples still run.

Run:

```bash
./scripts/regression/low/public_smoke.sh
```

## Full Run

```bash
./scripts/regression/run_all.sh
```

