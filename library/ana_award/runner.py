from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

# English/US homepage — do NOT use /amc/mileage-reservation/ (redirects to 404)
ANA_URL = "https://www.ana.co.jp/en/us/"


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "business"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    mid_days = max(14, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)

    lines = [
        f"Search for ANA Mileage Club AWARD flights from {origin} to {dest}, "
        f"{cabin} class, around {depart_date.strftime('%B %-d, %Y')}.",
        "",
        "=== IMPORTANT RULES ===",
        "- NEVER navigate to aswbe-i.ana.co.jp or aswbe.ana.co.jp directly.",
        "- The award search REQUIRES login. You MUST login first.",
        "- If CAPTCHA appears, report stuck immediately.",
        "",
        "=== STEP 1 — DISMISS COOKIE DIALOG ===",
        "If a 'Cookie Settings' dialog is covering the page:",
        "  Try: js_eval: document.querySelector('#onetrust-accept-btn-handler, .onetrust-close-btn-handler, button[class*=accept], .ot-sdk-btn')?.click()",
        "  If still showing, scroll down inside the dialog and look for an Accept button.",
        "  If nothing works, try: js_eval: document.querySelector('.onetrust-pc-dark-filter')?.remove(); document.querySelector('#onetrust-consent-sdk')?.remove()",
        "",
        "=== STEP 2 — LOGIN FIRST (MANDATORY) ===",
        "You MUST login before searching. The award search will block you without login.",
        "Look for 'Log In' or 'AMC Member' or 'ANA Mileage Club' in the header/menu.",
        "Click it.",
        "  - credentials for aswbe-i.ana.co.jp",
        "  - ANA Mileage Club number: 4135234365",
        "  - Enter the 10-digit member number and password",
        "  - Click Log In / Sign In",
        "  - wait 8",
        "If already logged in (you see a welcome message or member name), continue.",
        "",
        "=== STEP 3 — NAVIGATE TO AWARD SEARCH ===",
        "After login, find the award booking section.",
        "Look for:",
        "  a) 'Use Miles' tab in the booking widget on the homepage",
        "  b) 'Award Reservation' link",
        "  c) 'Book Flights with Miles' or 'ANA Mileage Club' in the menu",
        "Click it. A login session is required — the page will work now that you are logged in.",
        "wait 5",
        "",
        "=== STEP 4 — FILL SEARCH FORM ===",
        "  - Trip type: One Way (if available)",
        f"  - From/Departure: {origin} (type SFO, select from dropdown)",
        f"  - To/Arrival: {dest} (type {dest}, select from dropdown)",
        f"  - Date: around {depart_date.strftime('%B %-d')} (any nearby date is fine)",
        f"  - Cabin class: {cabin}",
        f"  - Passengers: {travelers}",
        "  - Click Search",
        "",
        "=== STEP 5 — WAIT FOR RESULTS ===",
        "wait 12",
        "",
        "=== STEP 6 — SCREENSHOT ===",
        "screenshot",
        "",
        "=== STEP 7 — REPORT AND DONE ===",
        "done",
        "",
        "Report what you see:",
        "A) CALENDAR: list dates with mileage prices",
        "   DATE: Mar 10 | XX,XXX miles",
        "B) FLIGHTS: list individual flights",
        "   FLIGHT: HH:MM-HH:MM | XX,XXX miles | stops | cabin",
        "C) SUMMARY:",
        f"   Cheapest {cabin}: [miles] on [date]",
        "",
        f"Budget: {max_miles:,} miles total ({max_miles // travelers:,} per person).",
        "If no results or CAPTCHA, report what you see on the page.",
    ]
    return "\n".join(lines)


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse agent free-text result into structured match dicts."""
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "business")
    travelers = int(inputs.get("travelers", 1))

    matches = []
    seen = set()

    # Pattern: "FLIGHT: HH:MM-HH:MM | XX,XXX miles"
    flight_pattern = re.compile(
        r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,]+)\s*(?:miles?|pts?|points?)',
        re.IGNORECASE,
    )
    for line in result_text.split("\n"):
        fm = flight_pattern.search(line)
        if fm:
            miles = int(fm.group(3).replace(",", ""))
            if miles >= 1000:
                key = f"{fm.group(1)}-{fm.group(2)}-{miles}"
                if key not in seen:
                    seen.add(key)
                    stops = ""
                    if re.search(r'\bnonstop\b', line, re.IGNORECASE):
                        stops = "Nonstop"
                    elif re.search(r'(\d)\s*stop', line, re.IGNORECASE):
                        sm = re.search(r'(\d)\s*stop', line, re.IGNORECASE)
                        stops = f"{sm.group(1)} stop(s)"
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "depart_time": fm.group(1).strip(),
                        "arrive_time": fm.group(2).strip(),
                        "stops": stops,
                        "notes": line.strip()[:150],
                    })

    # Pattern: "DATE: Mar 10 | XX,XXX miles"
    date_pattern = re.compile(
        r'DATE:.*?((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2})'
        r'.*?([\d,]+)\s*(?:miles?|pts?|points?)',
        re.IGNORECASE,
    )
    for line in result_text.split("\n"):
        dm = date_pattern.search(line.strip())
        if dm:
            date_label = dm.group(1).strip()
            miles = int(dm.group(2).replace(",", ""))
            if miles >= 1000:
                key = f"cal-{date_label}-{miles}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date_label": date_label,
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "source": "calendar",
                        "notes": line.strip()[:150],
                    })

    # Fallback: raw miles extraction
    if not matches:
        pts_pat = re.compile(r'([\d,]+)\s*(?:miles?|pts?|points?)\b', re.IGNORECASE)
        for line in result_text.split("\n"):
            pm = pts_pat.search(line)
            if pm:
                miles = int(pm.group(1).replace(",", ""))
                if miles >= 1000:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "notes": f"Raw: {line.strip()[:150]}",
                    })
                    break

    return matches


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "business"))
    travelers = int(inputs["travelers"])

    dest_str = ", ".join(destinations)
    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {dest_str}",
        f"Cabin: {cabin}",
    ]

    book_url = ANA_URL

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=ANA_URL,
            max_steps=50,
            airline="ana",
            inputs=inputs,
            max_attempts=1,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)
            observations.extend([
                "BrowserAgent run executed.",
                f"BrowserAgent status: {run_result.get('status', 'unknown') if isinstance(run_result, dict) else 'unknown'}",
                f"BrowserAgent steps: {run_result.get('steps', 'n/a') if isinstance(run_result, dict) else 'n/a'}",
            ])

            live_matches = _parse_matches(result_text, inputs)
            agent_matches = run_result.get("matches", []) if isinstance(run_result, dict) else []
            if agent_matches and not live_matches:
                live_matches = agent_matches

            for m in live_matches:
                if "booking_url" not in m:
                    m["booking_url"] = book_url

            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "booking_url": book_url,
                "summary": (
                    f"ANA award search: {len(live_matches)} flight(s) found "
                    f"under {max_miles:,} miles. "
                    + (f"Cheapest: {min(m['miles'] for m in live_matches):,} miles. "
                       if live_matches else "No matching flights. ")
                ),
                "raw_observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent adapter error: {agent_run['error']}")

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    matches = [{
        "route": f"{inputs['from']}-{destinations[0]}",
        "date": today.isoformat(),
        "miles": min(65000, max_miles),
        "travelers": travelers,
        "cabin": cabin,
        "mixed_cabin": False,
        "booking_url": book_url,
        "notes": "placeholder result",
    }]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "booking_url": book_url,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic ANA match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
