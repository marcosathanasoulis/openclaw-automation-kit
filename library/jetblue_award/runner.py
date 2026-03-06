from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

JETBLUE_URL = "https://www.jetblue.com"


def _booking_url(origin: str, dest: str, depart_date: date, travelers: int) -> str:
    """Construct a JetBlue deep-link for award search."""
    return (
        f"https://www.jetblue.com/booking/flights"
        f"?from={origin}&to={dest}"
        f"&depart={depart_date.isoformat()}"
        f"&isMultiCity=false&noOfRoute=1"
        f"&lang=en&adults={travelers}&children=0&infants=0"
        f"&sharedMarket=false&roundTrip=false"
        f"&usePoints=true"
    )


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    mid_days = max(7, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)
    # Advance to next Tuesday/Wednesday (JAL codeshare has sparse availability)
    weekday = depart_date.weekday()  # 0=Mon, 1=Tue, 2=Wed...
    if weekday not in (1, 2, 3):  # Not Tue/Wed/Thu
        days_to_tue = (1 - weekday) % 7
        if days_to_tue == 0:
            days_to_tue = 7
        depart_date = depart_date + timedelta(days=days_to_tue)
    range_end = date.today() + timedelta(days=days_ahead)

    # Build direct booking URL with usePoints=true
    book_url = _booking_url(origin, dest, depart_date, travelers)
    # Fallback date: 3 days later
    fallback_date = depart_date + timedelta(days=3)
    fallback_url = _booking_url(origin, dest, fallback_date, travelers)

    lines = [
        f"Search for JetBlue TrueBlue award flights {origin} to {dest}. "
        f"Check availability from now through {range_end.strftime('%B %-d, %Y')} "
        f"(starting around {depart_date.strftime('%B %-d')}).",
        "",
        "=== ACTION SEQUENCE ===",
        "",
        "STEP 1 - LOGIN:",
        "Look at the page. If you see a name or 'TrueBlue' member greeting, skip to STEP 2.",
        "If NOT logged in:",
        "  1a. Click 'Log in' or 'Sign in'.",
        "  1b. credentials for www.jetblue.com",
        "  1c. Enter email (marcos@athanasoulis.net) in email field.",
        "  1d. Enter password.",
        "  1e. Click 'Log in'.",
        "  1f. wait 5",
        "  1g. If email verification code is requested:",
        "      Use: read_email_code",
        "      This reads the latest verification code from Gmail.",
        "      Enter the code and submit.",
        "  1h. wait 5",
        "  1i. Close any popups or dialogs.",
        "",
        "STEP 2 - NAVIGATE TO AWARD SEARCH:",
        f"Your VERY NEXT ACTION must be: navigate {book_url}",
        "Do NOT touch the search form. Do NOT type in any fields. Do NOT use js_eval.",
        "The URL has usePoints=true so results will show in TrueBlue points.",
        "",
        "STEP 3 - WAIT FOR RESULTS:",
        "Your VERY NEXT ACTION must be: wait 15",
        "The results page needs time to load flight options with points prices.",
        "",
        "STEP 3b - IF NO FLIGHTS FOUND ON THIS DATE:",
        "If the page says 'No flights have been found' or 'No flights found':",
        f"  Your VERY NEXT ACTION must be: navigate {fallback_url}",
        "  wait 15",
        "  This tries a different date.",
        "",
        "STEP 3c - SCAN MULTIPLE DATES:",
        "JetBlue has a date carousel or calendar view at the top. Look for it.",
        "If you see a row of dates with prices (like 'Mar 10 — 45,000 pts'):",
        "  Read ALL dates currently shown.",
        "  Click '>' to advance. wait 5. Read all new dates.",
        "  Click '>' twice more, reading dates each time.",
        "If you do NOT see a date carousel, that is OK — report what you see for the current date.",
        "",
        "IMPORTANT — JAL CODESHARE FLIGHTS:",
        f"{dest} is a long-haul route. JetBlue may show Japan Airlines (JAL/JL) partner flights.",
        "Look for 'JL' or 'Japan Airlines' or 'Operated by Japan Airlines' in the results.",
        "If you see JAL flights, include them in your report — these are bookable with TrueBlue points.",
        "",
        "STEP 4 - SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "Do NOT try to click anything first. Just take the screenshot.",
        "",
        "STEP 5 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "Report:",
        "",
        "A) DATE/CALENDAR PRICES (if date strip visible):",
        "DATE: Mar 10 | XX,XXX points",
        "DATE: Mar 12 | XX,XXX points",
        "",
        "B) FLIGHT LIST for selected date:",
        "FLIGHT: HH:MM-HH:MM | XX,XXX points | Nonstop/1 stop | cabin | airline",
        "Include both JetBlue and JAL-operated flights.",
        "Report BOTH economy (Blue Basic/Blue) and business (Mint) fares if visible.",
        "",
        "C) SUMMARY:",
        "- Cheapest economy: [points] on [date]",
        "- Cheapest Mint/business: [points] on [date]",
        "- JAL partner flights: [yes/no, and how many]",
        "",
        f"Report all fares, even if above {max_miles:,} points.",
        "",
        "=== WARNINGS ===",
        "- Navigate to the URL in STEP 2 — do NOT fill the homepage search form.",
        "- For email 2FA, use the read_email_code action to get the code.",
        "- After screenshot, IMMEDIATELY do done.",
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
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    def _parse_pts(s: str) -> int:
        """Parse points from '55,000', '55k', '43.2k' formats."""
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

    matches = []
    seen = set()

    # Pattern 1: "FLIGHT: HH:MM-HH:MM | XX,XXX points"
    flight_pattern = re.compile(
        r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,.]+k?)\s*(?:points?|pts?)',
        re.IGNORECASE,
    )

    for line in result_text.split("\n"):
        fm = flight_pattern.search(line)
        if fm:
            points = _parse_pts(fm.group(3))
            if points >= 1000:
                key = f"{fm.group(1)}-{fm.group(2)}-{points}"
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
                        "miles": points,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "depart_time": fm.group(1).strip(),
                        "arrive_time": fm.group(2).strip(),
                        "stops": stops,
                        "notes": line.strip()[:150],
                    })

    # Pattern 2: Calendar "DATE: Mar 10 | XX,XXX points"
    date_pattern = re.compile(
        r'DATE:.*?(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?'
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2})'
        r'.*?([\d,]+)\s*(?:points?|pts?)',
        re.IGNORECASE,
    )
    for line in result_text.split("\n"):
        dm = date_pattern.search(line.strip())
        if dm:
            date_label = dm.group(1).strip()
            points = _parse_pts(dm.group(2))
            if points >= 1000:
                key = f"cal-{date_label}-{points}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "date_label": date_label,
                        "miles": points,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "source": "calendar",
                        "notes": line.strip()[:150],
                    })

    # Fallback: raw points extraction
    if not matches:
        pts_pat = re.compile(r'([\d,]+)\s*(?:points?|pts?)\b', re.IGNORECASE)
        for line in result_text.split("\n"):
            pm = pts_pat.search(line)
            if pm:
                points = _parse_pts(pm.group(1))
                if points >= 1000:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": points,
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
    travelers = int(inputs["travelers"])

    dest_str = ", ".join(destinations)
    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {dest_str}",
        f"Cabin: {cabin}",
    ]

    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, travelers)

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=JETBLUE_URL,
            max_steps=60,
            airline="jetblue",
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
                    f"JetBlue award search: {len(live_matches)} flight(s) found "
                    f"under {max_miles:,} points. "
                    + (f"Cheapest: {min(m['miles'] for m in live_matches):,} points. "
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
        "miles": min(30000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic JetBlue match(es) <= {max_miles} points",
        "raw_observations": observations,
        "errors": [],
    }
