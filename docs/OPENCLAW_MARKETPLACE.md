# OpenClaw Marketplace Publishing

This repo includes publishable skill folders under `skills/`.

Current skill packages:
- `skills/openclaw-web-automation` (unified: no-login + credentialed/2FA flows)

Local skill entrypoints:
- `python skills/openclaw-web-automation/scripts/run_query.py --query "..."`
- `python skills/openclaw-web-automation/scripts/run_query.py --query "..." --credential-refs '{...}'`

## 1. Install CLI and authenticate

```bash
npm i -g clawhub
clawhub login
```

## 2. Publish a skill

Example (unified skill):

```bash
clawhub publish ./skills/openclaw-web-automation \
  --slug openclaw-web-automation \
  --name "OpenClaw Web Automation" \
  --version 0.1.0 \
  --tags latest \
  --changelog "Initial marketplace release"
```

## 3. Verify install

```bash
clawhub install openclaw-web-automation
```

## 4. Update release

```bash
clawhub publish ./skills/openclaw-web-automation \
  --slug openclaw-web-automation \
  --version 0.1.1 \
  --tags latest \
  --changelog "Bug fixes"
```

## Notes
- Marketplace publishes skills, not full repositories.
- For credentialed flows, documentation must clearly require user-owned secrets + human-loop 2FA.
