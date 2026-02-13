# OpenClaw Marketplace Publishing

This repo includes publishable skill folders under `skills/`.

Current skill packages:
- `skills/openclaw-web-automation-basic` (no credentials)
- `skills/openclaw-award-search` (credentials + 2FA human-loop)

Local skill entrypoints:
- `python skills/openclaw-web-automation-basic/scripts/run_query.py --query "..."`
- `python skills/openclaw-award-search/scripts/run_query.py --query "..." --credential-refs '{...}'`

## 1. Install CLI and authenticate

```bash
npm i -g clawhub
clawhub login
```

## 2. Publish a skill

Example (web basic skill):

```bash
clawhub publish ./skills/openclaw-web-automation-basic \
  --slug openclaw-web-automation-basic \
  --name "OpenClaw Web Automation Basic" \
  --version 0.1.0 \
  --tags latest \
  --changelog "Initial marketplace release"
```

Example (award skill):

```bash
clawhub publish ./skills/openclaw-award-search \
  --slug openclaw-award-search \
  --name "OpenClaw Award Search" \
  --version 0.1.0 \
  --tags latest \
  --changelog "Initial marketplace release"
```

## 3. Verify install

```bash
clawhub install openclaw-web-automation-basic
```

## 4. Update release

```bash
clawhub publish ./skills/openclaw-web-automation-basic \
  --slug openclaw-web-automation-basic \
  --version 0.1.1 \
  --tags latest \
  --changelog "Bug fixes"
```

## Notes
- Marketplace publishes skills, not full repositories.
- Keep no-credential skill separate from credentialed skills.
- For credentialed skills, documentation must clearly require user-owned secrets + human-loop 2FA.
