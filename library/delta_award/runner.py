from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

DELTA_URL = "https://www.delta.com"

CABIN_MAP = {
    "economy": "Main Cabin",
    "premium_economy": "Delta Premium Select",
    "business": "Delta One",
    "first": "First Class",
}


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)
    month_display = depart_date.strftime("%B %Y")

    lines = [
        f"Search for Delta SkyMiles award flights {origin} to {dest} "
        f"around {month_display}, {cabin} class.",
        "",
        "STEP 1 - LOGIN:",
        "Go to delta.com. Click 'Log In' in the top right.",
        "Get credentials from keychain for www.delta.com.",
        "SkyMiles number: 9396260433.",
        "Enter SkyMiles number and password, click Log In.",
        "If already logged in (you see a name/greeting), skip login.",
        "Wait 3 seconds for the page to settle after login.",
        "",
        "STEP 2 - NAVIGATE TO AWARD SEARCH:",
        "On the delta.com homepage, you should see the booking widget.",
        "Click 'Shop with Miles' checkbox or toggle to enable miles search.",
        "Fill in the search form:",
        "",
        "  a) TRIP TYPE: Select 'One Way'.",
        "",
        f"  b) FROM: Type '{origin}' in the origin field. Select from dropdown.",
        "",
        f"  c) TO: Type '{dest}' in the destination field. Select from dropdown.",
        "",
        f"  d) DATE: Click the date field. Navigate to {depart_date.isoformat()}.",
        "     Select the date.",
        "",
    ]

    if travelers == 1:
        lines.append("  e) PASSENGERS: Leave at default (1 passenger).")
    else:
        lines.append(f"  e) PASSENGERS: Set to {travelers} passenger(s).")

    lines.extend([
        "",
        "  f) Click SUBMIT / SEARCH.",
        "",
        "STEP 3 - READ RESULTS:",
        "After results load, Delta shows a calendar with prices in miles.",
        f"Look for {cabin_display} fares.",
        "If there is a cabin filter, select the appropriate cabin class.",
        "",
        "Read the available flights and their miles prices.",
        f"Report which flights are under {max_miles:,} miles ({max_miles // travelers:,} per person).",
        "Include: departure time, arrival time, miles, stops, duration.",
        "If no flights are under the limit, say so clearly.",
        "When done reading results, use the done action with your findings.",
    ])
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
            url=DELTA_URL,
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
                "matches": run_result.get("matches", []),
                "summary": (
                    "BrowserAgent run completed for Delta award search. "
                    "Check raw_observations for flight details."
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
            "miles": min(25000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Delta match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
