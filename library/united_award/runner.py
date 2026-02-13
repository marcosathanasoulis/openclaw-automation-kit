from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

UNITED_URL = "https://www.united.com/en/us"


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)
    month_display = depart_date.strftime("%B %Y")

    lines = [
        f"Search for United award flights {origin} to {dest} around {month_display}, {cabin} class.",
        "",
        "STEP 1 - NAVIGATE TO AWARD SEARCH:",
        "Go to united.com/en/us. Check if already logged in (look for Hi greeting).",
        "If not logged in, that is OK -- we can still search.",
        "Click Book in the top nav. Select Book with miles checkbox/toggle.",
        "Fill in:",
        "  - One-way",
        f"  - From: {origin}",
        f"  - To: {dest}",
        f"  - Date: {depart_date.isoformat()}",
        f"  - Travelers: {travelers} adult(s)",
        f"  - Cabin: {cabin}",
        "Click Search/Find flights.",
        "",
        "STEP 2 - READ RESULTS:",
        "After results load, if there is a filter to hide mixed-cabin fares, enable it.",
        f"Sort by miles in {cabin} cabin.",
        "",
        "Report the first several flight options you see in this format:",
        "  Flight 1: departure HH:MM - arrival HH:MM, XX,XXX miles, carrier, stops",
        "  Flight 2: ...",
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
            url=UNITED_URL,
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
                    "BrowserAgent run completed for United award search. "
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
            "miles": min(80000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
