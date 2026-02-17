from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run
from openclaw_automation.result_extract import extract_award_matches_from_text

ANA_URL = "https://www.ana.co.jp/en/us/"
ANA_SEARCH_URL = "https://www.ana.co.jp/en/us/amc/award-rsrv/international/search/"

CABIN_MAP = {
    "economy": "Economy Class",
    "premium_economy": "Premium Economy",
    "business": "Business Class",
    "first": "First Class",
}


def _goal(inputs):
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    lines = [
        f"Search for ANA Mileage Club award flights {origin} to {dest} "
        f"on {depart_date.strftime('%B %-d, %Y')}, {cabin_display}, {travelers} passengers.",
        "",
        "=== ACTION SEQUENCE (follow EXACTLY, step by step) ===",
        "",
        "STEP 1 - LOGIN (required for award search):",
        "On the ANA homepage, look for a 'Log In' or 'Sign In' button/link.",
        "Click it to open the login form.",
        "If you see a login form with AMC Number and password fields:",
        "  1a. credentials for www.ana.co.jp",
        "  1b. Enter the ANA Mileage Club number (AMC Number) into the member number field",
        "  1c. Enter the password into the password field",
        "  1d. Click the 'Log In' button to submit",
        "  1e. wait 8",
        "If already logged in (you see a member name or welcome message), skip login.",
        "NOTE: The login may redirect to cam.ana.co.jp — that is normal.",
        "",
        "STEP 1b - NAVIGATE TO AWARD SEARCH:",
        f"After login, navigate to: {ANA_SEARCH_URL}",
        "This takes you directly to the international award search form.",
        "",
        "STEP 2 - WAIT FOR PAGE:",
        "Your VERY NEXT ACTION must be: wait 5",
        "",
        "STEP 3 - TAKE SCREENSHOT TO SEE FORM:",
        "Your VERY NEXT ACTION must be: screenshot",
        "Look at the form layout. You should see fields for departure/arrival, dates, cabin, passengers.",
        "",
        "STEP 4 - SET DEPARTURE CITY:",
        f"Click the departure city field and type '{origin}'.",
        "Select the matching airport from the dropdown suggestions.",
        f"If it says 'San Francisco' or shows '{origin}', that's correct.",
        "",
        "STEP 5 - SET ARRIVAL CITY:",
        f"Click the arrival/destination city field and type '{dest}'.",
        "Select the matching airport from the dropdown suggestions.",
        "",
        "STEP 6 - SET TRAVEL DATE:",
        f"Click the date field and navigate to {depart_date.strftime('%B %Y')}.",
        f"Select day {depart_date.day}.",
        "Use forward arrows to navigate months if needed.",
        "",
        "STEP 7 - SET CABIN CLASS:",
        f"If there is a cabin class dropdown, select '{cabin_display}'.",
        "If no cabin dropdown is visible, skip this step.",
        "",
        "STEP 8 - SET PASSENGERS:",
        f"If passengers is not already set to {travelers}, change it to {travelers}.",
        "Look for a passengers/adults field or +/- buttons.",
        "",
        "STEP 9 - SUBMIT SEARCH:",
        "Click the 'Search' or 'Search for Flights' button.",
        "",
        "STEP 10 - WAIT FOR RESULTS:",
        "Your VERY NEXT ACTION must be: wait 15",
        "ANA results take time to load.",
        "",
        "STEP 11 - TAKE SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "STEP 12 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "From the screenshot, report ALL visible flights with miles cost.",
        "Format: FLIGHT: [details] | [miles] miles | [cabin]",
        "",
        "If the page shows a calendar/date grid with availability indicators,",
        "report which dates show 'O' (available) vs 'X' (unavailable).",
        "",
        "=== CRITICAL NOTES ===",
        "- ANA's form may require clicking specific elements to reveal dropdowns",
        "- If a field doesn't respond to typing, try clicking it first",
        "- The departure/arrival fields may use autocomplete — wait for suggestions to appear",
        "- ANA award search REQUIRES login — always log in first",
        "- If you see a 'cookies' banner, dismiss it first",
    ]
    return "\n".join(lines)


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse ANA agent result text for flight matches."""
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "economy")
    travelers = int(inputs.get("travelers", 1))
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    matches = []

    # Pattern: miles amounts in text
    miles_pattern = re.compile(r'([\d,]+)\s*(?:miles|mi)', re.IGNORECASE)
    for line in result_text.split("\n"):
        mm = miles_pattern.search(line)
        if mm:
            miles = int(mm.group(1).replace(",", ""))
            if 1000 <= miles <= max_miles:
                matches.append({
                    "route": f"{origin}-{dest}",
                    "date": depart_date.isoformat(),
                    "miles": miles,
                    "travelers": travelers,
                    "cabin": cabin,
                    "mixed_cabin": False,
                    "notes": line.strip()[:150],
                })

    # Also try the standard extractor
    if not matches:
        matches = extract_award_matches_from_text(
            result_text,
            route=f"{origin}-{dest}",
            cabin=cabin,
            travelers=travelers,
            max_miles=max_miles,
        )

    return matches


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))
    travelers = int(inputs["travelers"])
    depart_date = today + timedelta(days=int(inputs["days_ahead"]))

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {', '.join(destinations)}",
        f"Cabin: {cabin}",
    ]

    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=ANA_URL,
            max_steps=40,
            airline="ana",
            inputs=inputs,
            max_attempts=2,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)

            live_matches = _parse_matches(result_text, inputs)

            observations.extend([
                "BrowserAgent run executed.",
                f"BrowserAgent status: {run_result.get('status', 'unknown') if isinstance(run_result, dict) else 'unknown'}",
                f"BrowserAgent steps: {run_result.get('steps', 'n/a') if isinstance(run_result, dict) else 'n/a'}",
                f"Extracted matches: {len(live_matches)}",
            ])
            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "summary": (
                    f"ANA award search: {len(live_matches)} flight(s) found. "
                    + (f"Best: {min(m['miles'] for m in live_matches):,} miles. "
                       if live_matches else "No matches extracted. ")
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
            "miles": min(65000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic ANA match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
