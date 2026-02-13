# In-Process: Skill Testing Coordination

## Who's Working On What

### Agent A (Claude Opus — this agent)
- [x] Credential resolution pipeline — env vars + keychain
- [ ] public_page_check with live URLs (no creds needed)
- [ ] github_signin_check with real credential_refs flow
- [ ] Wire credentials INTO runners (they currently ignore context["credentials"])
- [ ] Fix united_award runner to pass credentials to BrowserAgent

### Agent B (other agent)
- [ ] singapore_award runner testing via BrowserAgent on Mac Mini
- [ ] ana_award runner testing via BrowserAgent on Mac Mini
- [ ] bofa_alert — needs real implementation (currently stub)

## CDPLock Coordination
**CRITICAL**: Both agents MUST use CDPLock when running browser automations on Mac Mini.
- Lock file: `/tmp/browser_cdp.lock`
- The `browser_agent_adapter.py` already uses CDPLock automatically
- If testing directly via SSH + browser_agent.py, the CDPLock in browser_agent.py handles it
- **Never run two browser automations concurrently** — wait for lock release

## Environment Setup (Mac Mini)
```bash
# Required for BrowserAgent integration:
export OPENCLAW_USE_BROWSER_AGENT=true
export OPENCLAW_BROWSER_AGENT_MODULE=browser_agent
export OPENCLAW_BROWSER_AGENT_PATH=/Users/marcos/athanasoulis-ai-assistant/src/browser
export OPENCLAW_CDP_URL=http://127.0.0.1:9222
export OPENCLAW_CDP_LOCK_FILE=/tmp/browser_cdp.lock

# Credential resolution (env-based):
export OPENCLAW_SECRET_UNITED_USERNAME=marcosathanasoulis
# Or use keychain refs
```

## Status
- PR #1 (skill manifests + tests) — pending merge, CI should be green after lint fix
- All 32 tests passing locally
