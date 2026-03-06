from __future__ import annotations

import sys
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

CHASE_URL = "https://www.chase.com"


def _goal(inputs: Dict[str, Any]) -> str:
    check_type = str(inputs.get("check_type", "ur_points"))

    lines = [
        "Check Chase Ultimate Rewards points balance.",
        "",
        "STEP 1 - LOGIN:",
        "Go to chase.com. Click 'Sign in'.",
        "Get credentials from keychain for www.chase.com (account: marcosathanasoulis).",
        "IMPORTANT: Chase uses push notification 2FA. After entering credentials,",
        "you will see a 'We sent a push notification' message. Wait up to 60 seconds",
        "for the user to approve on their phone. Do NOT click 'Try another way'.",
        "",
        "STEP 2 - NAVIGATE TO REWARDS:",
    ]

    if check_type == "ur_points":
        lines.extend([
            "After login, look for 'Ultimate Rewards' or 'Points' in the dashboard.",
            "Click on the Ultimate Rewards section to see the points balance.",
            "Report the total UR points balance.",
        ])
    else:
        lines.extend([
            "After login, read all account balances from the dashboard.",
            "Report each account name and its current balance.",
            "Also navigate to Ultimate Rewards to get the points balance.",
        ])

    lines.extend([
        "",
        "STEP 3 - REPORT:",
        "Use the done action and report the UR points balance and any account balances seen.",
    ])
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    check_type = str(inputs.get("check_type", "ur_points"))

    observations: List[str] = [
        "OpenClaw session expected",
        f"Check type: {check_type}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = run_browser_agent_goal(
            goal=_goal(inputs),
            url=CHASE_URL,
            max_steps=40,
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
                "balances": run_result.get("balances", {}),
                "summary": (
                    "BrowserAgent run completed for Chase balance check. "
                    "Check raw_observations for balance details."
                ),
                "raw_observations": observations,
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
        "balances": {"ur_points": 0},
        "summary": "PLACEHOLDER: Chase balance check stub",
        "raw_observations": observations,
        "errors": [],
    }
