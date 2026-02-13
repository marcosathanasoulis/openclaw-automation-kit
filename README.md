# OpenClaw Automation Kit

A production-focused framework for browser automation scripts with a clear plugin contract, API-first execution model, and optional messaging hooks.

This project is designed for teams that want to:
- Run reliable browser automations using OpenClaw
- Share and version automations as scripts
- Expose a stable API for execution and scheduling
- Keep channel delivery (WhatsApp/iMessage/Slack/email) pluggable

## Why this exists

Most automation projects fail on structure: scripts are ad-hoc, outputs are inconsistent, and adding contributors is risky.

This repository provides:
- **Script contract**: manifest + input/output schemas + deterministic entrypoint
- **Execution engine**: validate inputs, run script, normalize result
- **API hooks**: send results to webhooks or any downstream connector
- **Contribution model**: PR-friendly layout, CI checks, test expectations

## Architecture

```mermaid
flowchart LR
  A[Client / Scheduler] --> B[Automation API]
  B --> C[Runner Engine]
  C --> D[OpenClaw Browser]
  C --> E[Script Plugin]
  E --> F[Result JSON]
  F --> G[Webhook / Connector]
```

## Repository layout

- `src/openclaw_automation/`: core engine and contract validator
- `examples/`: automation script examples (United, Singapore, ANA, BofA)
- `schemas/`: JSON schemas for manifests and run payloads
- `scripts/`: utility CLI wrappers
- `tests/`: contract + engine tests
- `docs/`: architecture and contribution docs

## Quickstart

### 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure keys locally:
```bash
cp .env.example .env
```
Then fill values per `docs/CONFIGURATION.md`.

### 2. Validate example script contracts

```bash
python -m openclaw_automation.cli validate --script-dir examples/united_award
python -m openclaw_automation.cli validate --script-dir examples/singapore_award
python -m openclaw_automation.cli validate --script-dir examples/ana_award
python -m openclaw_automation.cli validate --script-dir examples/bofa_alert
python -m openclaw_automation.cli validate --script-dir examples/github_signin_check
```

### 3. Run an example

```bash
python -m openclaw_automation.cli run \
  --script-dir examples/united_award \
  --input '{"from":"SFO","to":["AMS","LIS","FCO"],"max_miles":120000,"days_ahead":30,"travelers":2,"cabin":"economy","credential_refs":{"airline_username":"openclaw/united/username","airline_password":"openclaw/united/password"}}'
```

### 4. Run from plain English

```bash
python -m openclaw_automation.cli run-query \
  --query "Search ANA award travel economy from SFO to HND for 2 travelers in next 30 days under 120k miles" \
  --credential-refs '{"airline_username":"openclaw/ana/username","airline_password":"openclaw/ana/password"}'
```

This mode is optimized for award-travel style requests (airline + route + cabin + travelers + mileage cap).

## OpenClaw integration model

Scripts can call OpenClaw CLI (`openclaw browser ...`) or use a wrapper module. This kit does not hardcode a single OpenClaw strategy.

Current recommended reasoning path for smart browser automation is Claude vision-capable workflows.  
We welcome PRs for alternative providers/adapters (OpenAI, Gemini, local models), as long as they meet contract + test requirements.

Recommended pattern:
1. Script performs deterministic browser steps
2. Script emits normalized results (`matches`, `raw_observations`, `errors`)
3. API layer handles delivery and retries

See `examples/united_award/runner.py` for the starter structure.

## Human-in-the-loop CAPTCHA

Read `/Users/Marcos/code-projects/openclaw-automation-kit/docs/CAPTCHA_HUMAN_LOOP.md`.

Recommended pattern:
1. Script detects challenge and captures screenshot + metadata.
2. Engine sends challenge event to user via webhook adapter.
3. User replies with solve instructions/token (for example tile indexes).
4. Script resumes with short-lived `resume_token`.

Also see:
- `/Users/Marcos/code-projects/openclaw-automation-kit/docs/MESSAGING_HUMAN_LOOP_SETUP.md`
- `/Users/Marcos/code-projects/openclaw-automation-kit/docs/STARTER_EXAMPLES.md`

## Security and credentials

Read `/Users/Marcos/code-projects/openclaw-automation-kit/docs/CREDENTIALS_AND_2FA.md` before deploying.

It documents:
- macOS Keychain setup
- Linux/Windows secure store options
- webhook-based second-factor flow
- iMessage/WhatsApp connector scaffolding

Credential policy for this repo:
- Bring your own secrets store (OS keychain or cloud secret manager).
- Pass only `credential_refs` in script inputs.
- This project does **not** import/export credentials from password managers.

See also:
- `/Users/Marcos/code-projects/openclaw-automation-kit/docs/CONFIGURATION.md`
- `/Users/Marcos/code-projects/openclaw-automation-kit/DISCLAIMER.md`

## Acceptable use

We do **not** condone use of this project to automate:
- accounts, systems, or data you do not legitimately own or have explicit authorization to access
- private sites/services without permission

Use is intended for:
- public websites
- your own authorized accounts and workflows

## Connectors (bring your own)

This repo intentionally keeps delivery adapters separate.

Use the webhook output from the runner to integrate with:
- WhatsApp API
- BlueBubbles / iMessage bridges
- Slack
- Email

## Building new automations

Read `/Users/Marcos/code-projects/openclaw-automation-kit/docs/NEW_AUTOMATION_PLAYBOOK.md` for the recommended workflow to create production-grade new site automations.

## Concurrency and queueing

To keep automations from stepping on each other, use:
- centralized run queue
- resource locks (browser profile, site, messaging connector)
- explicit execution modes per script (`exclusive`, `profile_isolated`, `stateless`)

See:
- `/Users/Marcos/code-projects/openclaw-automation-kit/docs/QUEUE_AND_LOCKING.md`

## Contribution

Read:
- `CONTRIBUTING.md`
- `docs/SCRIPT_CONTRACT.md`
- `docs/API_DESIGN.md`
- `docs/CONFIGURATION.md`

All PRs must include schema-valid manifests and runnable tests.  
Provider/integration PRs must include at least one deterministic test case we can run in CI.

## License

Apache-2.0
