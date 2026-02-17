from __future__ import annotations

import os
import re
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run
from openclaw_automation.result_extract import extract_award_matches_from_text

ANA_URL = "https://www.ana.co.jp/en/us/"

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
        f"Search for ANA award flights {origin} to {dest} "
        f"on {depart_date.strftime('%B %-d, %Y')}, {cabin_display}, {travelers} passengers.",
        "",
        "=== ACTION SEQUENCE ===",
        "",
        "STEP 1 - LOGIN:",
        "You are on the ANA homepage (ana.co.jp/en/us/).",
        "Look at the top-right area for 'Log In', 'Sign In', 'ANA Mileage Club', or a person icon.",
        "If you see 'Welcome' or a member name, you are already logged in — skip to STEP 2.",
        "",
        "To log in:",
        "  1a. Click the 'Log In' or 'ANA Mileage Club' link/button in the header.",
        "  1b. wait 3",
        "  1c. You may see a login modal or be redirected to cam.ana.co.jp.",
        "  1d. credentials for www.ana.co.jp",
        "  1e. Enter the AMC Number (10-digit member number) into the member number field.",
        "  1f. Enter the password into the password field.",
        "  1g. Click 'Log In' / 'Sign In' to submit.",
        "  1h. wait 8",
        "",
        "If login fails or the page does not respond, try once more. If it still fails,",
        "proceed to STEP 2 anyway — some award info may be visible without login.",
        "",
        "STEP 2 - NAVIGATE TO AWARD BOOKING:",
        "Look in the navigation menu for 'ANA Mileage Club' > 'Use Miles' > 'Award Reservation'",
        "OR look for a 'Book Award' or 'Flight Awards' link.",
        "Click it and wait for the award search page to load.",
        "wait 5",
        "",
        "If the page shows 'This page cannot be displayed' or an error:",
        "  - Go back to the homepage.",
        "  - Look for 'Flight Award' or 'Award Ticket' in the booking tab area.",
        "  - Try clicking that link instead.",
        "  - wait 5",
        "",
        "STEP 3 - TAKE SCREENSHOT:",
        "screenshot",
        "Look at what form/page loaded. You need a search form with departure/arrival fields.",
        "",
        "STEP 4 - FILL DEPARTURE:",
        f"Click the departure/from field and type '{origin}'.",
        "Select the matching airport from suggestions.",
        "",
        "STEP 5 - FILL ARRIVAL:",
        f"Click the destination/to field and type '{dest}'.",
        "Select the matching airport from suggestions.",
        "",
        "STEP 6 - SET DATE:",
        f"Click the date field. Navigate to {depart_date.strftime('%B %Y')}.",
        f"Select day {depart_date.day}.",
        "",
        "STEP 7 - SET CABIN:",
        f"If there is a cabin class dropdown, select '{cabin_display}'.",
        "",
        "STEP 8 - SET PASSENGERS:",
        f"Set adults to {travelers} if not already set.",
        "",
        "STEP 9 - SEARCH:",
        "Click the 'Search' button.",
        "wait 15",
        "",
        "STEP 10 - SCREENSHOT AND REPORT:",
        "screenshot",
        "done",
        "",
        "Report ALL visible flights with miles cost:",
        "FLIGHT: [details] | [miles] miles | [cabin]",
        "",
        "If you see a calendar with O/X availability indicators:",
        "Report: DATE [date]: [O=available / X=unavailable]",
        "",
        "=== IMPORTANT ===",
        "- ANA's site is slow. Use wait commands generously.",
        "- The award system is at aswbe-i.ana.co.jp — it may take time to load.",
        "- If a field doesn't respond, try clicking it again after a short wait.",
        "- If the award search system is unavailable, report that in your done message.",
        "- Do NOT get stuck in loops. If something fails after 2 attempts, move on.",
    ]
    return "\n".join(lines)


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "economy")
    travelers = int(inputs.get("travelers", 1))
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    matches = []

    # Pattern: miles amounts
    miles_pattern = re.compile(r'([\d,]+)\s*(?:miles|mi)\b', re.IGNORECASE)
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

    # Also try standard extractor
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
        observations.append("Credential refs unresolved.")

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=ANA_URL,
            max_steps=45,
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
                f"Status: {run_result.get('status', 'unknown') if isinstance(run_result, dict) else 'unknown'}",
                f"Steps: {run_result.get('steps', 'n/a') if isinstance(run_result, dict) else 'n/a'}",
                f"Matches: {len(live_matches)}",
            ])
            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "summary": (
                    f"ANA award search: {len(live_matches)} flight(s) found. "
                    + (f"Best: {min(m['miles'] for m in live_matches):,} miles. "
                       if live_matches else "No matches. ")
                ),
                "raw_observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent error: {agent_run['error']}")

    print("WARNING: BrowserAgent not enabled.", file=sys.stderr)
    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": [],
        "summary": "PLACEHOLDER: ANA search not available",
        "raw_observations": observations,
        "errors": [],
    }
