from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

AEROMEXICO_URL = "https://www.aeromexico.com/en-us"
AEROMEXICO_BOOK_URL = "https://www.aeromexico.com/en-us"


def _booking_url() -> str:
    """AeroMexico booking page URL (deep-linking not supported due to reCAPTCHA)."""
    return AEROMEXICO_BOOK_URL


CABIN_MAP_AM = {
    "business": "Clase Premier",
    "economy": "Economy",
    "first": "Clase Premier",
}


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP_AM.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)

    lines = [
        f"Search for AeroMexico Club Premier award flights {origin} to {dest}, {cabin} class.",
        "",
        "STEP 1 - LOGIN:",
        "Go to aeromexico.com/en-us. Click 'Log in' or the user/profile icon in the top nav.",
        "IMPORTANT: AeroMexico has reCAPTCHA protection. You MUST type ALL text char-by-char",
        "using the press action for each character. Do NOT use js_eval or fill — those trigger CAPTCHA.",
        "",
        "Club Premier number: 00667826747",
        "Get password from keychain for www.aeromexico.com.",
        "Type the Club Premier number digit by digit using press action.",
        "Type the password char by char using press action.",
        "Click the login/submit button.",
        "Wait 3 seconds for login to complete.",
        "",
        "STEP 2 - NAVIGATE TO BOOKING FORM:",
        "After login, click 'Book' or 'Flights' in the top navigation.",
        "You should see the booking/search form at aeromexico.com/en-us/book.",
        "",
        "STEP 3 - FILL THE BOOKING FORM:",
        "Do these in order:",
        "",
        "  a) TRIP TYPE: Select 'One Way' (click the One Way radio/tab).",
        "",
        "  b) POINTS TOGGLE: Enable 'Use Club Premier points' or 'Redeem points'.",
        "     This is usually a toggle switch or checkbox near the top of the form.",
        "",
        f"  c) FROM: Click the origin field and type '{origin}'. Select from dropdown.",
        "",
        f"  d) TO: Click the destination field and type '{dest}'. Select from dropdown.",
        "",
        f"  e) DATE: Click the date field. Navigate the calendar to find {depart_date.isoformat()}.",
        f"     Select the date and confirm.",
        "",
    ]

    if travelers == 1:
        lines.append("  f) PASSENGERS: Leave at default (1 Adult). Do NOT change it.")
    else:
        lines.extend([
            f"  f) PASSENGERS: Click the passenger field. Use the + button to set {travelers} adults.",
            "     Close the passenger selector when done.",
        ])

    lines.extend([
        "",
        f"  g) CABIN: If there is a cabin/class selector, choose '{cabin_display}'.",
        "     If no cabin selector is visible, skip this — cabin selection may appear in results.",
        "",
        "  h) Click the SEARCH button (usually a large blue button at the bottom of the form).",
        "",
        "STEP 4 - READ RESULTS:",
        "Wait for results to load. Read available flights.",
        f"Report flights with their miles cost per person.",
        f"Note which flights are under {max_miles:,} miles total ({max_miles // travelers:,} per person).",
        "When done reading results, use the done action with your findings.",
        "",
        "IMPORTANT: Before calling done, note the current page URL from your browser.",
        "Include it in your response so we can generate a direct booking link.",
    ])
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic AeroMexico match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
