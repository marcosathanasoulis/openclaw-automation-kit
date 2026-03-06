from __future__ import annotations

import sys
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

BOFA_URL = "https://www.bankofamerica.com"


def _goal(inputs: Dict[str, Any]) -> str:
    query = str(inputs.get("query", "check balances"))

    lines = [
        f"Bank of America task: {query}",
        "",
        "STEP 1 - LOGIN:",
        "Go to bankofamerica.com. You should see the login form.",
        "Get credentials from keychain for www.bankofamerica.com (account: marcosathanasoulis).",
        "Type the Online ID and Passcode, then click Sign In.",
        "If 2FA is requested, handle it (SMS or email verification).",
        "",
        "STEP 2 - READ ACCOUNTS:",
        "After login, you should see the accounts overview.",
        "Read all account names and balances from the dashboard.",
        "Report each account with its current balance.",
        "",
        "STEP 3 - REPORT:",
        "Use the done action with all account balances found.",
    ]
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    query = str(inputs.get("query", "check balances"))

    observations: List[str] = [
        "OpenClaw session expected",
        f"Query: {query}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = run_browser_agent_goal(
            goal=_goal(inputs),
            url=BOFA_URL,
            max_steps=30,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            observations.extend(
                [
                    "BrowserAgent run executed.",
                    f"BrowserAgent status: {run_result.get('status', 'unknown')}",
                    f"BrowserAgent steps: {run_result.get('steps', 'n/a')}",
                    f"BrowserAgent trace_dir: {run_result.get('trace_dir', 'n/a')}",
                ]
            )
            return {
                "mode": "live",
                "real_data": True,
                "summary": (
                    "BrowserAgent run completed for BofA. "
                    "Check raw_observations for account details."
                ),
                "observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent adapter error: {agent_run['error']}")

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    return {
        "mode": "placeholder",
        "real_data": False,
        "summary": f"PLACEHOLDER: BofA runner received query: {query}",
        "observations": observations,
        "errors": [],
    }
