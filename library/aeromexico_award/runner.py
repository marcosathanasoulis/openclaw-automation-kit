from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

# The Spanish booking page has the points toggle (English page does NOT)
AEROMEXICO_AWARD_URL = "https://www.aeromexico.com/es-mx/reserva"
AEROMEXICO_BOOK_URL = "https://www.aeromexico.com/en-us"

CABIN_MAP_AM = {
    "business": "Clase Premier",
    "economy": "Turista",
    "first": "Clase Premier",
}

SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    mid_days = max(7, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)
    range_end = date.today() + timedelta(days=days_ahead)

    lines = [
        f"Search for AeroMexico CASH flights {origin} to {dest}. "
        f"Find the best prices from now through {range_end.strftime('%B %-d, %Y')} "
        f"(starting around {depart_date.strftime('%B %-d')}).",
        "",
        "NOTE: We are searching for CASH prices (not points/puntos).",
        "The page may be in English or Spanish.",
        "",
        "=== ACTION SEQUENCE ===",
        "",
        "STEP 1 - DISMISS POPUPS:",
        "If you see a cookie banner, click 'Accept' / 'Acepto'.",
        "Close any popups or dialogs.",
        "",
        "STEP 2 - FILL SEARCH FORM:",
        "  2a. Select 'One way' / 'Solo ida' trip type.",
        f"  2b. Enter origin: {origin}. Select from dropdown.",
        f"  2c. Enter destination: {dest}. Select from dropdown.",
        f"  2d. Select date: {depart_date.strftime('%B %-d, %Y')}.",
        "  2e. Click Search / 'Buscar vuelo'.",
        "",
        "STEP 3 - WAIT:",
        "Your VERY NEXT ACTION must be: wait 8",
        "",
        "STEP 4 - CHECK CALENDAR STRIP:",
        "Look at the date strip at the top of results showing prices for nearby dates.",
        "Note prices for visible dates.",
        "",
        "STEP 5 - SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "STEP 6 - REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "Report:",
        "",
        "A) CALENDAR PRICES (from date strip):",
        "DATE: Mar 10 | $XXX USD",
        "DATE: Mar 12 | $XXX USD",
        "",
        "B) FLIGHT LIST for selected date:",
        "FLIGHT: HH:MM-HH:MM | $XXX | Nonstop/1 stop | economy/business",
        "",
        "C) SUMMARY:",
        "- Cheapest economy: $XXX on [date]",
        "- Cheapest business: $XXX on [date]",
        "",
        "Report ALL visible prices in USD (or convert MXN to USD if shown in pesos).",
        "",
        "=== WARNINGS ===",
        "- Search CASH prices, NOT points/puntos.",
        "- Do NOT enable points toggle.",
        "- Use press action for typing if reCAPTCHA appears (type char by char).",
    ]
    return "\n".join(lines)


def _parse_result(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse BrowserAgent result text for AeroMexico award matches."""
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    max_miles = int(inputs["max_miles"])
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    matches = []
    if not result_text:
        return matches

    # Pattern 1: "FLIGHT: HH:MM-HH:MM | XX,XXX puntos | Directo"
    flight_pattern = re.compile(
        r'(?:FLIGHT:?\s*)?(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2}).*?'
        r'([\d,\.]+)\s*(?:points?|puntos?|miles?|millas?|pts?)',
        re.IGNORECASE,
    )

    for line in result_text.split("\n"):
        fm = flight_pattern.search(line)
        if fm:
            dep_time = fm.group(1)
            arr_time = fm.group(2)
            raw_miles = fm.group(3).replace(",", "")
            if "." in raw_miles:
                try:
                    miles = int(float(raw_miles) * 1000)
                except ValueError:
                    continue
            else:
                try:
                    miles = int(raw_miles)
                except ValueError:
                    continue
            if miles < 100:
                miles *= 1000
            if miles > max_miles:
                continue
            stops = ""
            if re.search(r'\b(nonstop|directo|sin\s*escala[s]?)\b', line, re.IGNORECASE):
                stops = "Nonstop"
            elif re.search(r'\b(1\s*(?:stop|escala))\b', line, re.IGNORECASE):
                stops = "1 stop"

            matches.append({
                "route": f"{origin}-{dest}",
                "date": depart_date.isoformat(),
                "miles": miles,
                "travelers": travelers,
                "cabin": cabin,
                "mixed_cabin": False,
                "depart_time": dep_time,
                "arrive_time": arr_time,
                "stops": stops,
                "booking_url": AEROMEXICO_BOOK_URL,
                "notes": line.strip()[:120],
            })

    # Pattern 2: Calendar prices "mar 15 | 12,500 puntos"
    if not matches:
        cal_pattern = re.compile(
            r'(?:mar|abr|may|jun|jul|ago|sep|oct|nov|dic|ene|feb)\w*\s+\d{1,2}.*?'
            r'([\d,\.]+)\s*(?:points?|puntos?|miles?|millas?|pts)',
            re.IGNORECASE,
        )
        for line in result_text.split("\n"):
            cm = cal_pattern.search(line)
            if cm:
                raw_val = cm.group(1).replace(",", "")
                if "." in raw_val:
                    try:
                        miles = int(float(raw_val) * 1000)
                    except ValueError:
                        continue
                else:
                    try:
                        miles = int(raw_val)
                    except ValueError:
                        continue
                if miles < 100:
                    miles *= 1000
                if 1000 <= miles <= max_miles:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "booking_url": AEROMEXICO_BOOK_URL,
                        "notes": line.strip()[:120],
                    })

    # Pattern 3: Generic point extraction (fallback)
    if not matches:
        point_pattern = re.compile(
            r'([\d,\.]+)\s*(?:points?|puntos?|miles?|millas?|pts)',
            re.IGNORECASE,
        )
        for line in result_text.split("\n"):
            pm = point_pattern.search(line)
            if pm:
                raw_val = pm.group(1).replace(",", "")
                if "." in raw_val:
                    try:
                        miles = int(float(raw_val) * 1000)
                    except ValueError:
                        continue
                else:
                    try:
                        miles = int(raw_val)
                    except ValueError:
                        continue
                if miles < 100:
                    miles *= 1000
                if 1000 <= miles <= max_miles:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "booking_url": AEROMEXICO_BOOK_URL,
                        "notes": line.strip()[:120],
                    })

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

    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        agent_run = adaptive_run(
            goal=_goal(inputs),
            url=AEROMEXICO_BOOK_URL,  # Use English site for cash search
            max_steps=45,
            airline="aeromexico",
            inputs=inputs,
            max_attempts=3,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            observations.extend([
                "BrowserAgent run executed.",
                f"BrowserAgent status: {run_result.get('status', 'unknown')}",
                f"BrowserAgent steps: {run_result.get('steps', 'n/a')}",
                f"BrowserAgent trace_dir: {run_result.get('trace_dir', 'n/a')}",
            ])

            result_text = run_result.get("result", "")
            live_matches = _parse_result(result_text, inputs)

            agent_matches = run_result.get("matches", [])
            if agent_matches and not live_matches:
                live_matches = agent_matches

            for m in live_matches:
                if "booking_url" not in m:
                    m["booking_url"] = AEROMEXICO_BOOK_URL

            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "booking_url": AEROMEXICO_BOOK_URL,
                "summary": (
                    f"AeroMexico award search completed. "
                    f"Found {len(live_matches)} match(es) under {max_miles:,} miles."
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
        "miles": min(50000, max_miles),
        "travelers": travelers,
        "cabin": cabin,
        "mixed_cabin": False,
        "booking_url": AEROMEXICO_BOOK_URL,
        "notes": "placeholder result",
    }]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "booking_url": AEROMEXICO_BOOK_URL,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic AeroMexico match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
