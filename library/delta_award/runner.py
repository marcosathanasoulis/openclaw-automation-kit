from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List
from urllib.parse import urlencode

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

DELTA_URL = "https://www.delta.com"

CABIN_MAP = {
    "economy": "Main Cabin",
    "premium_economy": "Delta Premium Select",
    "business": "Delta One",
    "first": "First Class",
}

DELTA_FARE_CLASS = {
    "economy": "COACH",
    "premium_economy": "PREMIUM_ECONOMY",
    "business": "DELTA_ONE",
    "first": "FIRST",
}


def _booking_url(origin: str, dest: str, depart_date: date, cabin: str, travelers: int) -> str:
    """Construct a Delta.com deep-link for the award search."""
    params = {
        "tripType": "ONE_WAY",
        "originCity": origin,
        "destinationCity": dest,
        "departureDate": depart_date.strftime("%m/%d/%Y"),
        "paxCount": str(travelers),
        "fareClass": DELTA_FARE_CLASS.get(cabin, "COACH"),
        "shopWithMiles": "true",
    }
    return f"https://www.delta.com/flight-search/book-a-flight?{urlencode(params)}"


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse agent free-text result into structured match dicts.

    Handles multiple formats the agent might produce:
    1. Structured: "DL1234 | 08:00-16:30 | Nonstop | 30,500 miles"
    2. Natural: "Flight DL1234 departs 8:00 AM arrives 4:30 PM, 30,500 miles, nonstop"
    3. Calendar: "30,500 miles" (fallback when only calendar data available)
    """
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "economy")
    travelers = int(inputs.get("travelers", 1))
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    matches = []

    # Pattern 1: Structured pipe-separated format
    # "DL1234 | 08:00-16:30 | Nonstop | 30,500 miles"
    pipe_pattern = re.compile(
        r'(?:DL|Delta\s*)\s*(\d{2,5})\s*\|'
        r'\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*\|'
        r'\s*(.*?)\|'
        r'\s*([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern 2: Natural language flight info
    # "Flight DL1234 departs 8:00 AM arrives 4:30 PM ... 30,500 miles"
    natural_pattern = re.compile(
        r'(?:flight\s+)?(?:DL|Delta\s*)[\s#]*(\d{2,5}).*?'
        r'(?:depart|dep|leave|from)[^\d]*(\d{1,2}:\d{2}(?:\s*[AP]M)?).*?'
        r'(?:arrive|arr|land|to)[^\d]*(\d{1,2}:\d{2}(?:\s*[AP]M)?).*?'
        r'([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern 3: Flight number + miles on same line (less structured)
    # "DL1234 ... 30,500 miles" or "Delta 1234 ... 30,500 miles"
    flight_miles_pattern = re.compile(
        r'(?:DL|Delta\s*)[\s#]*(\d{2,5}).*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern 4: Time range + miles (no flight number)
    # "8:00 AM - 4:30 PM ... 30,500 miles"
    time_miles_pattern = re.compile(
        r'(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    seen_flights = set()

    for line in result_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        match_data = None

        # Try patterns in order of specificity
        pm = pipe_pattern.search(line)
        if pm:
            miles = int(pm.group(5).replace(",", ""))
            if miles <= max_miles:
                match_data = {
                    "flight": f"DL{pm.group(1)}",
                    "depart_time": pm.group(2).strip(),
                    "arrive_time": pm.group(3).strip(),
                    "stops": pm.group(4).strip().rstrip("|").strip(),
                    "miles": miles,
                }
        if not match_data:
            nm = natural_pattern.search(line)
            if nm:
                miles = int(nm.group(4).replace(",", ""))
                if miles <= max_miles:
                    match_data = {
                        "flight": f"DL{nm.group(1)}",
                        "depart_time": nm.group(2).strip(),
                        "arrive_time": nm.group(3).strip(),
                        "stops": "",
                        "miles": miles,
                    }
        if not match_data:
            fm = flight_miles_pattern.search(line)
            if fm:
                miles = int(fm.group(2).replace(",", ""))
                if 1000 <= miles <= max_miles:
                    match_data = {
                        "flight": f"DL{fm.group(1)}",
                        "depart_time": "",
                        "arrive_time": "",
                        "stops": "",
                        "miles": miles,
                    }
        if not match_data:
            tm = time_miles_pattern.search(line)
            if tm:
                miles = int(tm.group(3).replace(",", ""))
                if 1000 <= miles <= max_miles:
                    match_data = {
                        "flight": "",
                        "depart_time": tm.group(1).strip(),
                        "arrive_time": tm.group(2).strip(),
                        "stops": "",
                        "miles": miles,
                    }

        if match_data:
            # Deduplicate by flight number
            key = match_data.get("flight") or f"{match_data['depart_time']}-{match_data['arrive_time']}"
            if key and key not in seen_flights:
                seen_flights.add(key)
                # Extract stops info if present in line
                if not match_data["stops"]:
                    if re.search(r'\bnonstop\b', line, re.IGNORECASE):
                        match_data["stops"] = "Nonstop"
                    else:
                        sm = re.search(r'(\d)\s*stop', line, re.IGNORECASE)
                        if sm:
                            match_data["stops"] = f"{sm.group(1)} stop(s)"

                matches.append({
                    "route": f"{origin}-{dest}",
                    "date": depart_date.isoformat(),
                    "miles": match_data["miles"],
                    "travelers": travelers,
                    "cabin": cabin,
                    "mixed_cabin": False,
                    "flight": match_data.get("flight", ""),
                    "depart_time": match_data.get("depart_time", ""),
                    "arrive_time": match_data.get("arrive_time", ""),
                    "stops": match_data.get("stops", ""),
                    "notes": line[:150],
                })

    # Pattern 5: Calendar format from Flexible Dates view
    # "CALENDAR: March 15 | 30,500 miles | Nonstop"
    if not matches:
        cal_pattern = re.compile(
            r'CALENDAR:.*?([\d,]+)\s*(?:miles|mi)',
            re.IGNORECASE,
        )
        for line in result_text.split("\n"):
            cm = cal_pattern.search(line)
            if cm:
                miles = int(cm.group(1).replace(",", ""))
                if 1000 <= miles <= max_miles:
                    stops = ""
                    if re.search(r'\bnonstop\b', line, re.IGNORECASE):
                        stops = "Nonstop"
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "stops": stops,
                        "notes": f"Calendar: {line.strip()[:150]}",
                    })

    # Pattern 6: Raw text extraction — look for the target date followed by miles
    # e.g., "Sun, Mar 15\n30,500\n+$6" or "Mar 15 ... 30,500 miles"
    if not matches:
        # Try to find date + miles in raw text (from js_eval output)
        raw_miles = re.compile(r'([\d,]+)\s*(?:miles|mi)', re.IGNORECASE)
        all_miles = []
        for line in result_text.split("\n"):
            for mm in raw_miles.finditer(line):
                miles = int(mm.group(1).replace(",", ""))
                if 1000 <= miles <= max_miles:
                    all_miles.append((miles, line.strip()[:150]))
        if all_miles:
            # Take the first mention (usually the target date price)
            miles, note = all_miles[0]
            matches.append({
                "route": f"{origin}-{dest}",
                "date": depart_date.isoformat(),
                "miles": miles,
                "travelers": travelers,
                "cabin": cabin,
                "mixed_cabin": False,
                "notes": f"Calendar-level: {note}",
            })

    # Fallback: if still no matches, scan for any miles amounts
    if not matches:
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
                        "notes": f"Raw extraction: {line.strip()[:150]}",
                    })
                    break  # Only take first/cheapest mention

    return matches


def _goal(inputs):
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)

    # Build the direct search URL
    search_url = _booking_url(origin, dest, depart_date, cabin, travelers)

    lines = [
        f"Search for Delta SkyMiles award flights {origin} to {dest} "
        f"on {depart_date.strftime('%B %-d, %Y')}, {cabin_display}.",
        "",
        "=== ACTION SEQUENCE (follow EXACTLY, step by step) ===",
        "",
        "STEP 1 - LOGIN (only if you see a 'Log In' button):",
        "If you see 'Log In' button:",
        "  1a. Click 'Log In'",
        "  1b. credentials for www.delta.com",
        "  1c. Type username into SkyMiles field",
        "  1d. Type password into password field",
        "  1e. Click 'Log In' button",
        "  1f. wait 5",
        "If already logged in (you see a name in top-right), skip to STEP 2.",
        "",
        "STEP 2 - NAVIGATE (ALWAYS DO THIS - DO NOT SKIP):",
        f"Your VERY NEXT ACTION must be: navigate to {search_url}",
        "This navigates to the booking form with pre-filled fields.",
        "You MUST do this even if SFO-BOS is already visible in the search bar.",
        "",
        "STEP 3 - WAIT FOR FORM:",
        "Your VERY NEXT ACTION must be: wait 3",
        "",
        "STEP 4 - VERIFY SHOP WITH MILES (CRITICAL):",
        "Look at the 'Shop with Miles' checkbox.",
        "If it is ALREADY checked/enabled (has a checkmark or is toggled on), DO NOT click it — skip to STEP 5.",
        "If it is NOT checked, click it to enable it.",
        "IMPORTANT: The URL should have pre-enabled this, so it is likely already checked. Only click if it is NOT checked.",
        "DO NOT click 'Find Flights' yet.",
        "",
        "STEP 5 - SUBMIT SEARCH:",
        "Your VERY NEXT ACTION must be: click the red 'Find Flights' button.",
        "",
        "STEP 6 - WAIT (CRITICAL - DO NOT SKIP):",
        "Your VERY NEXT ACTION must be: wait 12",
        "This is a separate action. The page needs time to load the calendar.",
        "",
        "STEP 6.5 - RECOVERY (if needed):",
        "If the page shows an error or crashes, try navigating to the URL again and repeat from STEP 3.",
        "",
        "STEP 7 - TAKE SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "The Flexible Dates calendar should show miles prices per date.",
        "",
        "STEP 8 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "From the screenshot, read the calendar prices and report:",
        "",
        f"For {depart_date.strftime('%B %-d, %Y')} and nearby dates, report:",
        "CALENDAR: [date] | [miles] miles | [Nonstop/1 Stop]",
        "",
        "Example:",
        "CALENDAR: Mar 15 | 30,500 miles | Nonstop",
        "CALENDAR: Mar 16 | 14,400 miles | Nonstop",
        "",
        "Also report the bottom bar info (e.g., 'From 30,500 miles +$6').",
        f"Focus on fares under {max_miles:,} miles.",
        "",
        "=== CRITICAL WARNINGS ===",
        "- STEP 2 (navigate) is MANDATORY. Always navigate to the URL even if form looks filled.",
        "- STEP 4 (Shop with Miles) MUST happen BEFORE STEP 5 (Find Flights).",
        "- If you skip Shop with Miles, the search returns CASH prices and crashes Chrome.",
        "- DO NOT click CONTINUE on the results. The individual flights page WILL crash Chrome.",
        "- DO NOT scroll on results pages.",
        "- The Flexible Dates calendar is safe. Just screenshot and report.",
        "- Follow steps 1-8 EXACTLY in order. Each step is ONE action.",
    ]
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))

    travelers = int(inputs["travelers"])
    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    dest_str = ", ".join(destinations)
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, cabin, travelers)

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {dest_str}",
        f"Cabin: {cabin}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=DELTA_URL,
            max_steps=40,
            airline="delta",
            inputs=inputs,
            max_attempts=3,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)
            observations.extend(
                [
                    "BrowserAgent run executed.",
                    f"BrowserAgent status: {run_result.get('status', 'unknown') if isinstance(run_result, dict) else 'unknown'}",
                    f"BrowserAgent steps: {run_result.get('steps', 'n/a') if isinstance(run_result, dict) else 'n/a'}",
                    f"BrowserAgent trace_dir: {run_result.get('trace_dir', 'n/a') if isinstance(run_result, dict) else 'n/a'}",
                ]
            )

            # Parse structured matches from agent's free-text result
            live_matches = _parse_matches(result_text, inputs)
            for m in live_matches:
                if "booking_url" not in m:
                    m["booking_url"] = book_url
            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "booking_url": book_url,
                "summary": (
                    f"Delta award search: {len(live_matches)} flight(s) found "
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
    matches = [
        {
            "route": f"{inputs['from']}-{destinations[0]}",
            "date": today.isoformat(),
            "miles": min(25000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Delta match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
