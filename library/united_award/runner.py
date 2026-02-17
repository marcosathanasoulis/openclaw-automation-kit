from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal
from openclaw_automation.result_extract import extract_award_matches_from_text

UNITED_URL = "https://www.united.com/en/us"


def _booking_url(
    origin: str,
    dest: str,
    depart_date: date,
    cabin: str,
    travelers: int,
    award: bool = False,
) -> str:
    """Build a United search URL.

    award=False gives a cash URL (no at= param).
    award=True adds at=1 (NOTE: at=1 currently causes skeleton loaders — avoid).
    """
    cabin_map = {"economy": "7", "business": "6", "first": "5"}
    sc = cabin_map.get(cabin, "7")
    url = (
        f"https://www.united.com/en/us/fsr/choose-flights?"
        f"f={origin}&t={dest}&d={depart_date.isoformat()}"
        f"&tt=1&clm=7&taxng=1&newp=1&sc={sc}"
        f"&px={travelers}&idx=1&st=bestmatches"
    )
    if award:
        url += "&at=1"
    return url


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs["max_miles"])
    mid_days = max(7, days_ahead // 2)
    depart_date = date.today() + timedelta(days=mid_days)

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
        "=== STEP 2 — NAVIGATE TO CASH SEARCH ===",
        f"Your VERY NEXT ACTION must be: navigate {cash_url}",
        "Do NOT use at=1 — it causes skeleton loaders that never load.",
        "This loads cash/dollar results first. We will switch to miles next.",
        "",
        "=== STEP 3 — WAIT FOR RESULTS TO LOAD ===",
        "wait 15",
        "Close any popups/dialogs that appear (click X or 'No thanks').",
        "You should see flight results with dollar prices. Verify results loaded.",
        "",
        "=== STEP 3B — SWITCH TO MILES PRICING ===",
        "Now switch the 'Show price in:' dropdown to 'Miles':",
        "  3b-1. Click the dropdown that says 'Money + Miles' in the search form bar.",
        "  3b-2. Select 'Miles' from the dropdown options.",
        "  3b-3. The DATE FIELD WILL GO BLANK after switching — this is expected!",
        f"  3b-4. Click the Dates field and type: {depart_date.strftime('%b %d')}",
        "  3b-5. If a calendar appears, click on the correct date.",
        f"  3b-6. The date should be {depart_date.strftime('%B %d, %Y')} or close to it.",
        "  3b-7. Click the 'Update' button.",
        "  3b-8. wait 15",
        "  If after this you still see dollar signs ($), report those prices anyway.",
        "",
        "If you CANNOT find a miles toggle (not logged in), that is OK.",
        "Report the cash prices instead.",
        "",
        "=== STEP 4 — SCREENSHOT ===",
        "Your VERY NEXT ACTION must be: screenshot",
        "",
        "=== STEP 5 — REPORT AND DONE ===",
        "Your VERY NEXT ACTION must be: done",
        "Report what you see. If prices are in miles, report:",
        "",
        "A) DATE STRIP:",
        "DAY M/D: XX,XXX miles",
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
        f"Report all fares, even if above {max_miles} miles.",
        "",
        "=== WARNINGS ===",
        "- For SMS 2FA, use read_sms_code (sender 26266).",
        "- After screenshot, IMMEDIATELY do done.",
        "- Do NOT scroll around looking for toggles or buttons.",
        "- Do NOT use js_eval.",
        "- NEVER report stuck. Always take screenshot and report what you see.",
    ]
    return "\n".join(lines)


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))

    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))
    travelers = int(inputs["travelers"])

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {', '.join(destinations)}",
        f"Cabin: {cabin}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    mid_days = max(7, int(inputs["days_ahead"]) // 2)
    depart_date = today + timedelta(days=mid_days)
    booking_url = _booking_url(
        inputs["from"], destinations[0], depart_date, cabin, travelers, award=True,
    )

    if browser_agent_enabled():
        agent_run = run_browser_agent_goal(
            goal=_goal(inputs),
            url=UNITED_URL,
            max_steps=60,
            trace=True,
            use_vision=True,
        )
        if agent_run["ok"]:
            run_result = agent_run.get("result") or {}
            extracted_matches = run_result.get("matches", [])
            if not extracted_matches:
                extracted_matches = extract_award_matches_from_text(
                    str(run_result.get("result", "")),
                    route=f"{inputs['from']}-{destinations[0]}",
                    cabin=cabin,
                    travelers=travelers,
                    max_miles=max_miles,
                )
            observations.extend(
                [
                    "BrowserAgent run executed.",
                    f"BrowserAgent status: {run_result.get('status', 'unknown')}",
                    f"BrowserAgent steps: {run_result.get('steps', 'n/a')}",
                    f"BrowserAgent trace_dir: {run_result.get('trace_dir', 'n/a')}",
                    f"Extracted matches: {len(extracted_matches)}",
                ]
            )
            summary_parts = [
                f"United award search: {len(extracted_matches)} flight(s) found",
            ]
            if extracted_matches:
                best = min(m["miles"] for m in extracted_matches)
                summary_parts.append(f"Best: {best:,} miles")
            return {
                "mode": "live",
                "real_data": True,
                "matches": extracted_matches,
                "booking_url": booking_url,
                "summary": ". ".join(summary_parts) + ".",
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
            "booking_url": booking_url,
            "notes": "placeholder result",
        }
    ]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "booking_url": booking_url,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
