from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List
from urllib.parse import urlencode

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

UNITED_URL = "https://www.united.com/en/us"

UNITED_CABIN_CODES = {
    "economy": "7",
    "premium_economy": "2",
    "business": "5",
    "first": "3",
}


def _booking_url(origin: str, dest: str, depart_date: date, cabin: str, travelers: int) -> str:
    """Construct a United.com deep-link for the award search results page."""
    params = {
        "f": origin,
        "t": dest,
        "d": depart_date.isoformat(),
        "tt": "1",          # one-way
        "clm": "7",         # cabin class
        "taxng": "1",
        "newp": "1",
        "sc": UNITED_CABIN_CODES.get(cabin, "7"),
        "px": str(travelers),
        "idx": "1",
        "st": "bestmatches",
    }
    return f"https://www.united.com/en/us/fsr/choose-flights?{urlencode(params)}"


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)

    search_url = _booking_url(origin, dest, depart_date, cabin, travelers)

    lines = [
        f"Search for United award flights {origin} to {dest} "
        f"on {depart_date.strftime('%B %-d, %Y')}, {cabin} class.",
        "",
        "=== ACTION SEQUENCE (follow EXACTLY, step by step) ===",
        "",
        "STEP 1 - CHECK LOGIN:",
        "Look at the page. If you see 'Hi [name]' or a greeting in the top-right, you are logged in. Skip to STEP 2.",
        "If NOT logged in (you see 'Sign in' or person icon):",
        "  1a. Click the person/profile icon or 'Sign in' link in the header.",
        "  1b. credentials for www.united.com",
        "  1c. Enter MileagePlus number ka388724 in the username field.",
        "  1d. Click Continue.",
        "  1e. wait 3",
        "  1f. Enter the password in the password field that appears.",
        "  1g. Click 'Sign in'.",
        "  1h. wait 5",
        "  1i. If a dialog or popup appears, close it (click X).",
        "",
        "STEP 2 - NAVIGATE TO SEARCH RESULTS (ALWAYS DO THIS):",
        f"Your VERY NEXT ACTION must be: navigate to {search_url}",
        "This URL goes DIRECTLY to the search results page with cash prices.",
        "",
        "STEP 3 - WAIT FOR RESULTS:",
        "Your VERY NEXT ACTION must be: wait 8",
        "The results page needs time to load flight options.",
        "",
        "STEP 4 - SWITCH TO MILES VIEW:",
        "Look at the 'Show price in:' dropdown near the top of the results.",
        "If it already shows 'Miles', SKIP directly to STEP 7 (screenshot).",
        "If it shows 'Money', click the dropdown and select 'Miles'.",
        "Then: wait 5",
        "",
        "STEP 5 - VERIFY MILES ARE SHOWING:",
        "Look at the flight prices. If you see miles amounts (e.g. '80,000 miles'), go to STEP 7.",
        "If prices still show dollar amounts ($), click the blue 'Update' button to re-run the search.",
        "Then: wait 10",
        "IMPORTANT: Do NOT re-select Miles from the dropdown again. Just click Update once.",
        "",
        "STEP 6 - FINAL CHECK:",
        "If the page still shows dollar prices after Update, the date may have cleared.",
        f"Re-enter the date {depart_date.strftime('%B %-d')} and click Update again.",
        "Then: wait 10",
        "",
        "STEP 7 - TAKE SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "This will show the flight results with pure miles prices.",
        "",
        "STEP 8 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "From the screenshot and page content, report ALL visible flights.",
        "Format each flight as:",
        f"FLIGHT: HH:MM-HH:MM | XX,XXX miles | Nonstop/1 stop | carrier | {cabin}",
        "",
        f"Focus on flights under {max_miles:,} miles.",
        "If the page shows 'Sign in' instead of results, note that.",
        "If miles prices aren't showing, report what IS visible.",
        "",
        "=== CRITICAL WARNINGS ===",
        "- STEP 2 is MANDATORY. Always navigate to the direct URL.",
        "- Do NOT select 'Miles' from the dropdown more than ONCE. If you already selected it, move on.",
        "- If you see dollar prices after selecting Miles, click 'Update' button — do NOT re-select Miles.",
        "- Do NOT fill in the booking form from scratch. Use the direct URL first.",
        "- If a 'Sign in' popup appears, close it and continue.",
        "- After taking your screenshot in STEP 7, IMMEDIATELY do 'done' in STEP 8.",
        "- Follow steps 1-8 EXACTLY in order. Do not repeat steps.",
    ]
    return "\n".join(lines)


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse agent free-text result into structured match dicts."""
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "economy")
    travelers = int(inputs.get("travelers", 1))
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    matches = []
    seen = set()

    # Pattern 1: "FLIGHT: HH:MM-HH:MM | XX,XXX miles | ..."
    flight_pattern = re.compile(
        r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,]+)\s*(?:miles|mi)\b',
        re.IGNORECASE,
    )

    # Pattern 2: "UA123 ... XX,XXX miles"
    ua_pattern = re.compile(
        r'(?:UA|United)\s*#?\s*(\d{1,5}).*?([\d,]+)\s*(?:miles|mi)\b',
        re.IGNORECASE,
    )

    for line in result_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like combo pricing ($ + miles)
        if re.search(r'\$[\d,]+\s*\+\s*[\d,]+\s*miles', line, re.IGNORECASE):
            continue

        match_data = None

        fm = flight_pattern.search(line)
        if fm:
            miles = int(fm.group(3).replace(",", ""))
            if 1000 <= miles <= max_miles:
                match_data = {
                    "depart_time": fm.group(1).strip(),
                    "arrive_time": fm.group(2).strip(),
                    "miles": miles,
                }

        if not match_data:
            um = ua_pattern.search(line)
            if um:
                miles = int(um.group(2).replace(",", ""))
                if 1000 <= miles <= max_miles:
                    match_data = {
                        "flight": f"UA{um.group(1)}",
                        "depart_time": "",
                        "arrive_time": "",
                        "miles": miles,
                    }

        if match_data:
            key = f"{match_data.get('depart_time', '')}-{match_data.get('arrive_time', '')}-{match_data['miles']}"
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
                    "date": depart_date.isoformat(),
                    "miles": match_data["miles"],
                    "travelers": travelers,
                    "cabin": cabin,
                    "mixed_cabin": False,
                    "flight": match_data.get("flight", ""),
                    "depart_time": match_data.get("depart_time", ""),
                    "arrive_time": match_data.get("arrive_time", ""),
                    "stops": stops,
                    "notes": line[:150],
                })

    # Fallback: raw miles extraction (skip combo pricing)
    if not matches:
        miles_pat = re.compile(r'([\d,]+)\s*(?:miles|mi)\b', re.IGNORECASE)
        for line in result_text.split("\n"):
            if re.search(r'\$[\d,]+\s*\+', line):
                continue
            mm = miles_pat.search(line)
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
                        "notes": f"Raw: {line.strip()[:150]}",
                    })
                    break

    return matches


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

    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    travelers = int(inputs["travelers"])
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, cabin, travelers)

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=UNITED_URL,
            max_steps=45,
            airline="united",
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

            live_matches = _parse_matches(result_text, inputs)

            # Also check agent-extracted matches
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
                    f"United award search: {len(live_matches)} flight(s) found "
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
            "miles": min(80000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
