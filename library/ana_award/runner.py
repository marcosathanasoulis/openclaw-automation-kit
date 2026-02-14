from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

# Use the English/US path — less bot-sensitive per LEARNINGS.md
ANA_URL = "https://www.ana.co.jp/en/us/amc/mileage-reservation/"


def _booking_url() -> str:
    """ANA's award search form URL (deep-linking params not supported)."""
    return ANA_URL


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    # Use midpoint of range for broader calendar coverage
    mid_days = max(7, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)
    range_end = date.today() + timedelta(days=days_ahead)
    month_display = depart_date.strftime("%B %Y")

    lines = [
        f"Search for ANA Mileage Club award flights {origin} to {dest}, {cabin} class. "
        f"Check availability from now through {range_end.strftime('%B %-d, %Y')} "
        f"(starting around {month_display}).",
        "",
        "STEP 1 - LOGIN (if needed):",
        "Check if already logged in (look for a name/welcome message).",
        "If not logged in, get credentials from keychain for aswbe-i.ana.co.jp.",
        "ANA Mileage Club number: 4135234365.",
        "",
        "STEP 2 - FILL SEARCH FORM:",
        "The ANA award search form should be visible.",
        f"  - Departure: {origin} (San Francisco)",
        f"  - Arrival: {dest}",
        f"  - Departure date: {depart_date.isoformat()}",
        f"  - Cabin: {cabin}",
        f"  - Passengers: {travelers} adult(s)",
        "  - Trip type: One-way if available, otherwise round-trip",
        "NOTE: ANA may default to round-trip. That is OK.",
        "Click Search.",
        "",
        "STEP 3 - SCAN CALENDAR:",
        "After results load, look for the calendar/date view showing availability.",
        "ANA shows a monthly calendar with available dates highlighted.",
        "Note ALL dates that show availability and their miles prices.",
        "If you can navigate forward to see more dates, do so once.",
        "Then: wait 3",
        "",
        "STEP 4 - TAKE SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "STEP 5 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "Report:",
        "",
        "A) CALENDAR DATES (list all dates with availability):",
        "DATE: Mar 10 | XX,XXX miles (Regular/Low season)",
        "DATE: Mar 15 | XX,XXX miles (Regular/Low season)",
        "",
        "B) FLIGHT LIST for selected date (if flight details are shown):",
        "FLIGHT: HH:MM-HH:MM | XX,XXX miles | Nonstop/1 stop | cabin",
        "",
        "C) SUMMARY:",
        "- Cheapest business: [miles] on [date]",
        "- Cheapest economy (if visible): [miles] on [date]",
        "",
        f"ANA shows miles per person. Focus on fares under {max_miles:,} total "
        f"({max_miles // travelers:,} per person).",
        "",
        "CAPTCHA HANDLING:",
        "If a CAPTCHA appears (image selection, reCAPTCHA, etc.):",
        "  1. Take a screenshot immediately.",
        "  2. Report stuck with message: 'CAPTCHA appeared - screenshot taken'.",
        "  The system will send the screenshot to the user to solve manually.",
    ]
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))

    travelers = int(inputs["travelers"])
    book_url = _booking_url()
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
            url=ANA_URL,
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
            live_matches = run_result.get("matches", [])
            for m in live_matches:
                if "booking_url" not in m:
                    m["booking_url"] = book_url
            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "booking_url": book_url,
                "summary": (
                    "BrowserAgent run completed for ANA award search. "
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
            "miles": min(65000, max_miles),
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "booking_url": book_url,
            "notes": "placeholder result",
        }
    ]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "booking_url": book_url,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic ANA match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
