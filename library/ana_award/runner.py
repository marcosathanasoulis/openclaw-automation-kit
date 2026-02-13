from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

ANA_URL = "https://aswbe-i.ana.co.jp/international_asw/pages/award/search/roundtrip/award_search_roundtrip_input.xhtml?CONNECTION_KIND=JPN&LANG=en"


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
    depart_date = date.today() + timedelta(days=days_ahead)
    month_display = depart_date.strftime("%B %Y")

    lines = [
        f"Search for ANA Mileage Club award flights {origin} to {dest} around {month_display}, {cabin} class.",
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
        "STEP 3 - READ RESULTS:",
        "After results load, read the available flights.",
        "ANA shows miles per person. Report what you see.",
        f"Note which flights are under {max_miles:,} miles total ({max_miles // travelers:,} per person).",
        "If CAPTCHA appears, report stuck.",
        "When done reading results, use the done action with your findings.",
        "",
        "IMPORTANT: Before calling done, note the current page URL from your browser.",
        "Include it in your response so we can generate a direct booking link.",
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
