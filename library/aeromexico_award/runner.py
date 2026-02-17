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
    _cabin_display = CABIN_MAP_AM.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)
    month_spanish = SPANISH_MONTHS[depart_date.month]
    day_num = depart_date.day

    lines = [
        f"Book an AeroMexico award flight {origin} to {dest}, {cabin} class, "
        f"{depart_date.strftime('%B %-d, %Y')}.",
        "",
        "THIS PAGE IS IN SPANISH. You are on the Spanish booking page (es-mx/reserva).",
        "The user is logged in ('Hola, Marcos' in top nav).",
        "",
        "=== ACTION SEQUENCE (follow EXACTLY, step by step) ===",
        "",
        "STEP 1 — DISMISS COOKIES:",
        "If you see a cookie banner at the bottom with 'Acepto', click it.",
        "If no cookie banner, skip to step 2.",
        "",
        "STEP 2 — SELECT TRIP TYPE:",
        "Click the trip type dropdown (says 'Ida y vuelta').",
        "Select 'Sólo ida' (One way).",
        "",
        "STEP 3 — SET ORIGIN:",
        f"Click the 'Origen' field. Type '{origin}'. Select from dropdown.",
        "",
        "STEP 4 — SET DESTINATION:",
        f"Click the 'Destino' field. Type '{dest}'. Select from dropdown.",
        "",
        "STEP 5 — SET DATE:",
        "Click the 'Fechas' / '¿Cuándo?' field.",
        f"Navigate the calendar to {month_spanish} {depart_date.year}.",
        f"Click day {day_num}.",
        "",
        "STEP 6 — ENABLE POINTS TOGGLE (CRITICAL):",
        "Below the form fields, you will see text: 'Usar mis Puntos Aeroméxico Rewards'",
        "with a small toggle switch next to it.",
        "If the toggle is OFF (gray/white circle on the left), CLICK it to turn it ON (blue/green).",
        "If the toggle is already ON (blue/green circle on the right), skip this.",
        "The toggle is NOT in the accessibility tree — use mouse_click at approximately x=345, y=520",
        "if you cannot find it in the snapshot. Then take a screenshot to verify it turned on.",
        "",
        "STEP 7 — SEARCH:",
        "Click 'Buscar vuelo' (the big pink/magenta button).",
        "",
        "STEP 8 — WAIT:",
        "Your VERY NEXT ACTION must be: wait 8",
        "",
        "STEP 9 — SWITCH TO POINTS VIEW:",
        "On the results page, look for 'Buscar vuelos con' with two buttons: 'Pesos' and 'Puntos'.",
        "Click the 'Puntos' button to see point prices instead of cash.",
        "If it's already showing points, skip this.",
        "",
        "STEP 10 — WAIT FOR UPDATE:",
        "Your VERY NEXT ACTION must be: wait 5",
        "",
        "STEP 11 — TAKE SCREENSHOT:",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "STEP 12 — REPORT AND DONE:",
        "Your VERY NEXT ACTION must be: done",
        "From the screenshot, report ALL visible flights with their POINTS cost.",
        "Format each flight as:",
        "FLIGHT: HH:MM-HH:MM | XX,XXX puntos | Directo/1 escala | cabin",
        "",
        f"Note which flights cost under {max_miles:,} puntos per person.",
        "Include the calendar prices at the top of the page if visible.",
        "",
        "=== CRITICAL WARNINGS ===",
        "- Do NOT skip step 6 (toggle) or step 9 (Puntos switch).",
        "- Do NOT navigate to aeromexico.com/en-us — stay on the Spanish page.",
        "- Do NOT scroll on results pages.",
        "- Do NOT waste steps verifying the toggle via JS — just click it.",
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
            url=AEROMEXICO_AWARD_URL,
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
