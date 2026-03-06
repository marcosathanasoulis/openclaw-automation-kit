from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run

# Use English page for simpler navigation; cash prices are fine per user
AEROMEXICO_URL = "https://www.aeromexico.com/en-us"
AEROMEXICO_BOOK_URL = "https://www.aeromexico.com/en-us"

CABIN_MAP_AM = {
    "business": "Business/Premier",
    "economy": "Economy",
    "first": "Business/Premier",
}


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP_AM.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    # Start of window, not end
    start_date = date.today() + timedelta(days=7)
    end_date = date.today() + timedelta(days=days_ahead)
    max_miles = int(inputs.get("max_miles", 999999))
    travelers = int(inputs["travelers"])

    lines = [
        f"Search for AeroMexico Club Premier award flights {origin} to {dest}, "
        f"{cabin_display} class, {travelers} adults.",
        f"Find availability from {start_date.strftime('%b %-d')} through {end_date.strftime('%b %-d, %Y')}.",
        "",
        "=== IMPORTANT: AeroMexico uses reCAPTCHA — type ALL text fields char-by-char using press action ===",
        "=== Use the 'press' action for each character (not 'type' or 'fill') to bypass bot detection ===",
        "",
        "=== STEP 1 — LOGIN TO CLUB PREMIER ===",
        "Navigate to https://www.aeromexico.com/en-us/my-account",
        "wait 5",
        "Look for 'Sign In' or 'Log In' or 'Club Premier' login button. Click it.",
        "wait 3",
        "credentials for www.aeromexico.com",
        "Use PRESS action (char-by-char) to type the Club Premier number (username).",
        "Use PRESS action (char-by-char) to type the password.",
        "Click the Login button. wait 8.",
        "If you see a welcome message or your name, login succeeded.",
        "",
        "=== STEP 2 — NAVIGATE TO AWARD SEARCH ===",
        "Navigate to https://www.aeromexico.com/en-us/flights/award-flights",
        "wait 5",
        "OR: look for 'Redeem Miles' or 'Award Flights' in the menu and click it.",
        "",
        "=== STEP 3 — FILL SEARCH FORM ===",
        "Click on 'One Way' if not selected.",
        "wait 2",
        f"Click origin field. Use PRESS to type '{origin}' char-by-char. Select from dropdown.",
        f"Click destination field. Use PRESS to type '{dest}' char-by-char. Select from dropdown.",
        f"Click date field. Use PRESS to type date char-by-char or navigate calendar to {start_date.strftime('%B %d, %Y')}.",
        f"Set passengers to {travelers}.",
        "",
        "=== STEP 4 — SEARCH ===",
        "Click the Search button. wait 15.",
        "",
        "=== STEP 5 — SCAN DATE RANGE ===",
        "After results load, look for a date strip or calendar showing multiple dates.",
        "If you see a date carousel, read ALL dates with their miles prices.",
        "Advance the calendar (click >) to see more dates up to 30 days ahead.",
        "",
        "=== STEP 6 — SCREENSHOT AND REPORT ===",
        "screenshot",
        "done",
        "Report ALL visible flights:",
        "FLIGHT: HH:MM-HH:MM | XX,XXX miles | stops | cabin | date",
        "DATE_STRIP: [date]: [miles] | [date]: [miles] | ...",
        "",
        f"Report all results even if above {max_miles:,} miles.",
        "",
        "=== CRITICAL NOTES ===",
        "- ALWAYS use press action (char-by-char) for ALL form inputs — not type/fill",
        "- If you see an error about bot detection, take a screenshot and report done",
        "- If the form requires selecting from a dropdown, click the dropdown first",
        "- Do NOT use js_eval to fill forms",
        "- Do NOT submit with form.submit() — click the actual Search button",
    ]
    return "\n".join(lines)


def _parse_result(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse AeroMexico results — handles both points and cash prices."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    max_miles = int(inputs["max_miles"])
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    matches = []
    if not result_text:
        return matches

    # Pattern 1: Points/miles
    points_pattern = re.compile(
        r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2}).*?'
        r'([\d,\.]+)\s*(?:points?|puntos?|miles?|millas?|pts)',
        re.IGNORECASE,
    )

    # Pattern 2: Cash prices (MXN or USD)
    cash_pattern = re.compile(
        r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2}).*?'
        r'[\$MXN\s]*([\d,\.]+)\s*(?:MXN|USD|pesos?|\$)',
        re.IGNORECASE,
    )

    # Pattern 3: Generic "time range + number"

    for line in result_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try points first
        pm = points_pattern.search(line)
        if pm:
            raw_val = pm.group(3).replace(",", "")
            try:
                miles = int(float(raw_val))
            except ValueError:
                continue
            if miles < 100:
                miles *= 1000
            if 1000 <= miles <= max_miles:
                stops = ""
                if re.search(r'\b(nonstop|direct|directo)\b', line, re.IGNORECASE):
                    stops = "Nonstop"
                elif re.search(r'\b1\s*stop\b', line, re.IGNORECASE):
                    stops = "1 stop"
                matches.append({
                    "route": f"{origin}-{dest}",
                    "date": depart_date.isoformat(),
                    "miles": miles,
                    "travelers": travelers,
                    "cabin": cabin,
                    "mixed_cabin": False,
                    "depart_time": pm.group(1),
                    "arrive_time": pm.group(2),
                    "stops": stops,
                    "notes": line[:120],
                })
            continue

        # Try cash pattern
        cm = cash_pattern.search(line)
        if cm:
            raw_val = cm.group(3).replace(",", "")
            try:
                price = float(raw_val)
            except ValueError:
                continue
            stops = ""
            if re.search(r'\b(nonstop|direct|directo)\b', line, re.IGNORECASE):
                stops = "Nonstop"
            elif re.search(r'\b1\s*stop\b', line, re.IGNORECASE):
                stops = "1 stop"
            matches.append({
                "route": f"{origin}-{dest}",
                "date": depart_date.isoformat(),
                "miles": 0,  # Cash price, no miles
                "cash_price": price,
                "currency": "MXN" if "MXN" in line.upper() or "pesos" in line.lower() else "USD",
                "travelers": travelers,
                "cabin": cabin,
                "mixed_cabin": False,
                "depart_time": cm.group(1),
                "arrive_time": cm.group(2),
                "stops": stops,
                "notes": line[:120],
            })

    # Fallback: just look for any points/miles mentions
    if not matches:
        point_pattern = re.compile(
            r'([\d,\.]+)\s*(?:points?|puntos?|miles?|millas?|pts)',
            re.IGNORECASE,
        )
        for line in result_text.split("\n"):
            pm = point_pattern.search(line)
            if pm:
                raw = pm.group(1).replace(",", "")
                try:
                    miles = int(float(raw))
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
                        "notes": line.strip()[:120],
                    })

    # Last fallback: cash prices without time
    if not matches:
        cash_line = re.compile(r'[\$]([\d,\.]+)', re.IGNORECASE)
        for line in result_text.split("\n"):
            cm = cash_line.search(line)
            if cm and ("flight" in line.lower() or ":" in line):
                raw = cm.group(1).replace(",", "")
                try:
                    price = float(raw)
                except ValueError:
                    continue
                if price > 50:  # Skip tiny prices
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": 0,
                        "cash_price": price,
                        "currency": "USD",
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "notes": line.strip()[:120],
                    })

    return matches


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    cabin = str(inputs.get("cabin", "economy"))

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
            url=AEROMEXICO_URL,
            max_steps=35,
            airline="aeromexico",
            inputs=inputs,
            max_attempts=1,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            observations.extend([
                "BrowserAgent run executed.",
                f"Status: {run_result.get('status', 'unknown')}",
                f"Steps: {run_result.get('steps', 'n/a')}",
            ])

            result_text = run_result.get("result", "")
            live_matches = _parse_result(result_text, inputs)

            for m in live_matches:
                if "booking_url" not in m:
                    m["booking_url"] = AEROMEXICO_BOOK_URL

            # Separate points and cash matches for summary
            pts_matches = [m for m in live_matches if m.get("miles", 0) > 0]
            cash_matches = [m for m in live_matches if m.get("cash_price")]

            summary_parts = [f"AeroMexico search: {len(live_matches)} flight(s) found"]
            if pts_matches:
                best = min(m["miles"] for m in pts_matches)
                summary_parts.append(f"Best: {best:,} points")
            if cash_matches:
                best_cash = min(m["cash_price"] for m in cash_matches)
                curr = cash_matches[0].get("currency", "USD")
                summary_parts.append(f"Cheapest: ${best_cash:,.0f} {curr}")

            return {
                "mode": "live",
                "real_data": True,
                "matches": live_matches,
                "booking_url": AEROMEXICO_BOOK_URL,
                "summary": ". ".join(summary_parts) + ".",
                "raw_observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent error: {agent_run['error']}")

    print("WARNING: BrowserAgent not enabled.", file=sys.stderr)
    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": [],
        "booking_url": AEROMEXICO_BOOK_URL,
        "summary": "PLACEHOLDER: AeroMexico search not available",
        "raw_observations": observations,
        "errors": [],
    }
