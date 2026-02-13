from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

AEROMEXICO_URL = "https://www.aeromexico.com/en-us"


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)

    lines = [
        f"Search for AeroMexico Club Premier award flights {origin} to {dest}, {cabin} class.",
        "",
        "STEP 1 - LOGIN:",
        "Go to aeromexico.com/en-us. Click 'Log in' or the user icon.",
        "Get credentials from keychain for www.aeromexico.com (account: 00667826747).",
        "IMPORTANT: AeroMexico has reCAPTCHA. Type credentials char-by-char using press action,",
        "NOT js_eval or fill. Human-like input avoids CAPTCHA triggers.",
        "After login, look for Club Premier balance display.",
        "",
        "STEP 2 - NAVIGATE TO AWARD SEARCH:",
        "Click 'Book' or 'Flights'. Enable 'Use Club Premier points' toggle.",
        "Fill in:",
        "  - One-way",
        f"  - From: {origin}",
        f"  - To: {dest}",
        f"  - Date: {depart_date.isoformat()}",
        f"  - Travelers: {travelers} adult(s)",
        f"  - Cabin: {cabin}",
        "Click Search.",
        "",
        "STEP 3 - READ RESULTS:",
        "After results load, read the available flights.",
        "Report flight options with their miles cost.",
        f"Note which flights are under {max_miles:,} miles total ({max_miles // travelers:,} per person).",
        "If no flights are under the limit, say so clearly.",
        "When done reading results, use the done action with your findings.",
    ]
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))

    dest_str = ", ".join(destinations)
    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {dest_str}",
        f"Cabin: {cabin}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = run_browser_agent_goal(
            goal=_goal(inputs),
            url=AEROMEXICO_URL,
            max_steps=60,
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
                "matches": run_result.get("matches", []),
                "summary": (
                    "BrowserAgent run completed for AeroMexico award search. "
                    "If matches is empty, extraction mapping is still in progress."
                ),
                "raw_observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent adapter error: {agent_run['error']}")

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    matches = [
        {
            "route": f"{inputs['from']}-{destinations[0]}",
            "date": today.isoformat(),
            "miles": min(50000, max_miles),
            "travelers": int(inputs["travelers"]),
            "cabin": cabin,
            "mixed_cabin": False,
            "notes": "placeholder result",
        }
    ]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic AeroMexico match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
