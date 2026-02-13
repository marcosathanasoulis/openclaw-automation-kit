from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

SIA_URL = "https://www.singaporeair.com"

CABIN_MAP = {
    "business": "Business",
    "economy": "Economy",
    "first": "First",
    "premium_economy": "Premium Economy",
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
        f"Search for Singapore Airlines KrisFlyer award flights {origin} to {dest} around {month_display}, {cabin_display} class.",
        "",
        "STEP 1 - LOGIN:",
        "Go to singaporeair.com. Login with KrisFlyer number: 8814147288.",
        "Get password from keychain for www.singaporeair.com.",
        "If already logged in (you see a welcome message or your name), skip login.",
        "",
        "STEP 2 - NAVIGATE TO REDEMPTION SEARCH:",
        "After login, click 'Redeem flights' or 'Book with miles' link.",
        "You should land on the flight redemption search form.",
        "",
        "STEP 3 - FILL THE SEARCH FORM:",
        "The SIA search form is a Vue.js app. Some fields are readonly and need special handling.",
        "",
        "  a) ONE-WAY: Click the 'One-way' radio button or tab.",
        "",
        "  b) FROM FIELD: Type 'San Francisco' in the origin field slowly (delay between keys).",
        "     Wait 2-3 seconds for the autocomplete dropdown to appear.",
        "     Click the suggestion containing 'San Francisco' or 'SFO'.",
        "",
        "  c) TO FIELD: Type the destination city name in the destination field slowly.",
        "     Wait 2-3 seconds for autocomplete. Click the matching suggestion.",
        "",
        f"  d) CLASS FIELD: The class field (name='flightClass') is READONLY.",
        f"     Use js_eval to set it: document.querySelector('[name=flightClass]').value = '{cabin_display}';",
        f"     Also try: document.querySelector('#flightClass2').value = '{cabin_display}';",
        "     If that does not work, look for a Vue component and use vue_interact.",
        "",
        "  e) DATE: Click the date input field to open the calendar.",
        f"     Navigate to {month_display} using the month dropdown or arrows.",
        f"     Select the departure date ({depart_date.isoformat()}).",
        "     Check the 'One-way' checkbox in the calendar if present.",
        "     Click 'Done' to close the calendar.",
        "",
        f"  f) PASSENGERS: Set to {travelers} adult(s).",
        "",
        "  g) Click 'Search' button.",
        "",
        "STEP 4 - READ RESULTS:",
        "The results page shows a date slider with 7 days at a time.",
        "Read the prices for the visible dates.",
        "For each date, note:",
        "  - Saver pricing (~68,500 miles) vs Advantage pricing (~154,000 miles) vs Waitlist vs No availability",
        "",
        "Report available dates in format:",
        "  Date 1: Saver 68,500 | Date 2: Advantage 154,000 | Date 3: none | ...",
        f"Note which flights are under {max_miles:,} miles total ({max_miles // travelers:,} per person).",
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
            url=SIA_URL,
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
                    "BrowserAgent run completed for Singapore award search. "
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
            "miles": min(70000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Singapore match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
