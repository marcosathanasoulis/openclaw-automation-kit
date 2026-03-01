from __future__ import annotations

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
    mid_days = days_ahead
    depart_date = date.today() + timedelta(days=mid_days)

    cash_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=False)

    lines = [
        f"Search for United MileagePlus award flights {origin} to {dest}, {travelers} adult(s), {cabin} class.",
        f"Date: {depart_date.strftime(chr(37)+chr(66)+chr(32)+chr(37)+chr(45)+chr(100)+chr(44)+chr(32)+chr(37)+chr(89))}",
        "",
        "=== STEP 1 - LOGIN ===",
        "Look at top-right of page. If you see Hi [name] or miles balance: skip to STEP 2.",
        "If NOT logged in:",
        "  1a. Click Sign In or person icon.",
        "  1b. credentials for www.united.com",
        "  1c. Enter MileagePlus number: ka388724",
        "  1d. Click Continue. wait 5.",
        "  1e. Enter password. Click Sign in. wait 8.",
        "  1f. If SMS 2FA requested: read_sms_code sender=26266 keyword=united.",
        "      Enter code. wait 5. Check Remember this browser if visible. Submit.",
        "",
        "=== STEP 2 - NAVIGATE TO RESULTS ===",
        f"navigate {cash_url}",
        "wait 15",
        "Close any popups (X button).",
        "",
        "=== STEP 3 - SWITCH TO MONEY+MILES ===",
        "Look for Show price in: Money | Money + Miles tabs above the flight results.",
        "3a. Click the Money + Miles tab.",
        "3b. The date field may go blank. If blank, re-enter the date and select it.",
        "3c. Click the Update button (always do this, even if date was not blank).",
        "3d. wait 15. Results will reload with miles+cash pricing.",
        "3e. Take a screenshot to see the results.",
        "",
        "=== STEP 4 - CHECK FOR SHOW CALENDAR ===",
        "Look for a Show calendar button or link near the flight list.",
        "If found: click it, wait 5, take screenshot.",
        "This shows a calendar with prices for multiple dates.",
        "",
        "=== STEP 5 - REPORT PRICES ===",
        "Take a screenshot.",
        "done",
        "Report ALL flight prices you see in the format:",
        "",
        "FLIGHTS for [date]:",
        "FLIGHT: [depart]-[arrive] | [miles]k miles + $[cash] | [stops] | [cabin]",
        "",
        "If a calendar was shown, also report:",
        "CALENDAR: [Mon Feb 28]: [miles]k miles | [Tue Mar 1]: [miles]k miles | ...",
        "",
        "CRITICAL RULES:",
        "  - Only report exact prices you SAW on screen.",
        "  - Do NOT round numbers (report 72,000 not 72k).",
        "  - If Business class shows no miles (only cash), note that.",
        f"  - Report all fares even above {max_miles:,} miles.",
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
