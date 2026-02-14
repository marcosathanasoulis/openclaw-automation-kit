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


def _booking_url(origin: str, dest: str, depart_date: date, cabin: str, travelers: int, award: bool = True) -> str:
    """Construct a United.com deep-link for the search results page."""
    params = {
        "f": origin,
        "t": dest,
        "d": depart_date.isoformat(),
        "tt": "1",          # one-way
        "clm": "7",         # cabin class
        "taxng": "1",
        "newp": "1",
        "sc": "7",  # Always search economy so all cabin prices are visible
        "px": str(travelers),
        "idx": "1",
        "st": "bestmatches",
    }
    if award:
        params["at"] = "1"  # award travel mode (miles) — requires login
    return f"https://www.united.com/en/us/fsr/choose-flights?{urlencode(params)}"


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    # Use midpoint of range so the date strip shows more of the window
    mid_days = max(7, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)
    range_end = date.today() + timedelta(days=days_ahead)

    award_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)
    cash_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=False)

    lines = [
        f"Search for United award flights {origin} to {dest}, {travelers} adult(s), {cabin} class. "
        f"Check availability around {depart_date.strftime('%B %-d, %Y')}.",
        "",
        "=== STEP 1 — LOGIN ===",
        "Look at the page. If you see 'Hi [name]' or a greeting, skip to STEP 2.",
        "If NOT logged in:",
        "  1a. Click the person/profile icon or 'Sign in'.",
        "  1b. credentials for www.united.com",
        "  1c. Type MileagePlus number ka388724.",
        "  1d. Click 'Continue'.",
        "  1e. wait 5",
        "  1f. Type the password.",
        "  1g. Click 'Sign in'.",
        "  1h. wait 8",
        "  1i. If SMS 2FA is requested: read_sms_code (sender 26266).",
        "      Enter code and click Submit/Verify.",
        "      wait 5",
        "  1j. Close any popups (X or 'No thanks').",
        "",
        "  IF LOGIN FAILS ('Something went wrong', error message, etc.):",
        "  - Do NOT retry login. Close the dialog.",
        "  - Go to STEP 2 anyway (cash prices will show instead of miles).",
        "",
        "=== STEP 2 — NAVIGATE TO AWARD SEARCH ===",
        f"Your VERY NEXT ACTION must be: navigate {award_url}",
        "This URL includes at=1 for award/miles mode.",
        "Do NOT fill the homepage search form. Do NOT toggle anything.",
        "",
        "=== STEP 3 — WAIT AND HANDLE RESULTS ===",
        "wait 15",
        "If a 'Sign in' dialog appears over the results:",
        "  - If you already logged in successfully, close it (click X).",
        "  - If login failed, click 'Show flights with money' or close the dialog.",
        "",
        "If you see an ERROR PAGE ('unable to complete your request'):",
        f"  Your VERY NEXT ACTION must be: navigate {cash_url}",
        "  wait 15",
        "",
        "=== STEP 4 — SCREENSHOT ===",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "=== STEP 5 — REPORT AND DONE ===",
        "Your VERY NEXT ACTION must be: done",
        "Report what you see. If prices are in miles, report:",
        "",
        "A) DATE STRIP:",
        "DATE: Mon Mar 10 | XX,XXX miles",
        "",
        "B) FLIGHTS:",
        "FLIGHT: HH:MM-HH:MM | XX,XXX miles | stops | cabin",
        "",
        "C) SUMMARY:",
        "- Cheapest economy: [miles] on [date]",
        "- Cheapest business: [miles] on [date]",
        "",
        "If prices show in dollars instead of miles, still report them:",
        "FLIGHT: HH:MM-HH:MM | $XXX | stops | cabin",
        "Note: 'Prices shown in USD, not miles'",
        "",
        f"Report all fares, even if above {max_miles:,} miles.",
        "",
        "=== WARNINGS ===",
        "- For SMS 2FA, use read_sms_code (sender 26266).",
        "- After screenshot, IMMEDIATELY do done.",
        "- Do NOT scroll around looking for toggles or buttons.",
        "- Do NOT use js_eval.",
        "- NEVER report stuck. Always take screenshot and report what you see.",
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

    def _parse_miles(s: str) -> int:
        """Parse miles from various formats: '55,000', '55k', '43.2k', '250k'."""
        s = s.strip().replace(",", "")
        if s.lower().endswith("k"):
            try:
                return int(float(s[:-1]) * 1000)
            except ValueError:
                return 0
        try:
            return int(s)
        except ValueError:
            return 0

    # Pattern 1: "FLIGHT: HH:MM-HH:MM | XX,XXX miles | ..."
    flight_pattern = re.compile(
        r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,.]+k?)\s*(?:miles|mi)\b',
        re.IGNORECASE,
    )

    # Pattern 2: "UA123 ... XX,XXX miles"
    ua_pattern = re.compile(
        r'(?:UA|United)\s*#?\s*(\d{1,5}).*?([\d,.]+k?)\s*(?:miles|mi)\b',
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
            miles = _parse_miles(fm.group(3))
            if miles >= 1000:
                match_data = {
                    "depart_time": fm.group(1).strip(),
                    "arrive_time": fm.group(2).strip(),
                    "miles": miles,
                }

        if not match_data:
            um = ua_pattern.search(line)
            if um:
                miles = _parse_miles(um.group(2))
                if miles >= 1000:
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

    # Pattern 3: "DATE: Mon Mar 10 | XX,XXX miles" (calendar strip entries)
    date_pattern = re.compile(
        r'DATE:\s*(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?'
        r'((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2})|(?:\d{1,2}/\d{1,2}))'
        r'.*?([\d,.]+k?)\s*(?:miles|mi)',
        re.IGNORECASE,
    )
    for line in result_text.split("\n"):
        dm = date_pattern.search(line.strip())
        if dm:
            date_label = dm.group(1).strip()
            miles = _parse_miles(dm.group(2))
            if miles >= 1000:
                # Try to parse the date
                try:
                    from datetime import datetime as dt
                    parsed = dt.strptime(f"{date_label} {date.today().year}", "%b %d %Y")
                    iso_date = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    iso_date = depart_date.isoformat()
                key = f"cal-{date_label}-{miles}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": iso_date,
                        "date_label": date_label,
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "source": "calendar_strip",
                        "notes": line.strip()[:150],
                    })

    # Fallback: raw miles extraction (skip combo pricing)
    if not matches:
        miles_pat = re.compile(r'([\d,.]+k?)\s*(?:miles|mi)\b', re.IGNORECASE)
        for line in result_text.split("\n"):
            if re.search(r'\$[\d,]+\s*\+', line):
                continue
            mm = miles_pat.search(line)
            if mm:
                miles = _parse_miles(mm.group(1))
                if miles >= 1000:
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

    # Cash price fallback: "FLIGHT: HH:MM-HH:MM | $XXX | ..."
    if not matches:
        cash_pattern = re.compile(
            r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
            r'.*?\$\s*([\d,.]+)',
            re.IGNORECASE,
        )
        for line in result_text.split("\n"):
            cm = cash_pattern.search(line)
            if cm:
                try:
                    price = float(cm.group(3).replace(",", ""))
                except ValueError:
                    continue
                if price > 10:
                    key = f"cash-{cm.group(1)}-{cm.group(2)}-{price}"
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
                            "cash_price": price,
                            "currency": "USD",
                            "travelers": travelers,
                            "cabin": cabin,
                            "mixed_cabin": False,
                            "depart_time": cm.group(1).strip(),
                            "arrive_time": cm.group(2).strip(),
                            "stops": stops,
                            "notes": f"Cash: {line.strip()[:150]}",
                        })

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
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, cabin, travelers, award=False)

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=UNITED_URL,
            max_steps=60,
            airline="united",
            inputs=inputs,
            max_attempts=1,
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
