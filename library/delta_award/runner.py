from __future__ import annotations

import os
import re
import sys
import threading
import time
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


def _login_goal() -> str:
    return "\n".join([
        "Login to Delta.com SkyMiles account.",
        "",
        "1. Look at the top right of the page.",
        "2. If you see a name/greeting (like 'Hi Marcos'), you are already logged in. Report done.",
        "3. If you see 'Log In' or 'Sign Up':",
        "   a. Click 'Log In'",
        "   b. credentials for www.delta.com",
        "   c. Type the SkyMiles number (username) into the SkyMiles/username field",
        "   d. Type the password into the password field",
        "   e. Click the 'Log In' submit button",
        "   f. wait 5",
        "4. After login, report done.",
        "5. Do NOT navigate anywhere else after login.",
    ])


def _extract_results_js():
    """JS to extract flight results from the Delta results page."""
    return """() => {
        const results = [];

        // Method 1: Flexible Dates calendar cells
        const cells = document.querySelectorAll(
            '[class*="calendar"] td, [class*="Calendar"] td, ' +
            '[class*="flex-date"], [class*="FlexDate"], ' +
            '.offering-cell, .flex-dates-cell, ' +
            '[data-testid*="calendar"], [class*="offering"]'
        );
        cells.forEach(c => {
            const text = c.textContent.trim().replace(/\\s+/g, ' ');
            if (text.length > 2 && text.length < 200 && /\\d/.test(text)) {
                results.push({type: 'calendar', text: text});
            }
        });

        // Method 2: Flight cards/rows
        const flights = document.querySelectorAll(
            '[class*="flight-card"], [class*="FlightCard"], ' +
            '[class*="trip-card"], [class*="TripCard"], ' +
            '[class*="flight-info"], [class*="FlightInfo"], ' +
            '.bound-content, [data-testid*="flight"]'
        );
        flights.forEach(f => {
            const text = f.textContent.trim().replace(/\\s+/g, ' ');
            if (text.length > 10 && text.length < 500) {
                results.push({type: 'flight', text: text});
            }
        });

        // Method 3: All text lines containing "miles" or prices
        const bodyText = document.body.innerText || '';
        const lines = bodyText.split('\\n');
        const relevant = [];
        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.length > 3 && trimmed.length < 200) {
                if (/mile/i.test(trimmed) || /\\b\\d{1,3},?\\d{3}\\b/.test(trimmed)) {
                    relevant.push(trimmed);
                }
            }
        }

        // Method 4: From/starting prices at bottom
        const fromPrices = [];
        const fromElements = document.querySelectorAll(
            '[class*="price"], [class*="Price"], ' +
            '[class*="miles"], [class*="Miles"], ' +
            '[class*="from-price"], [class*="starting"]'
        );
        fromElements.forEach(el => {
            const text = el.textContent.trim();
            if (/\\d/.test(text) && text.length < 100) {
                fromPrices.push(text);
            }
        });

        return {
            calendar: results.filter(r => r.type === 'calendar').map(r => r.text).slice(0, 30),
            flights: results.filter(r => r.type === 'flight').map(r => r.text).slice(0, 15),
            milesLines: relevant.slice(0, 40),
            fromPrices: fromPrices.slice(0, 20),
            url: window.location.href,
            title: document.title
        };
    }"""


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse agent or Playwright result text into structured match dicts."""
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

    # Pattern: various miles formats
    miles_pattern = re.compile(r'([\d,]+)\s*(?:miles?|mi)\b', re.IGNORECASE)

    # Pattern: structured flight info
    flight_pattern = re.compile(
        r'(?:DL|Delta\s*)[\s#]*(\d{2,5}).*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern: time range + miles
    time_miles = re.compile(
        r'(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern: calendar-style "date miles"
    cal_pattern = re.compile(
        r'(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[\s,]+)?'
        r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}|\d{1,2}/\d{1,2})'
        r'.*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    for line in result_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try flight pattern first
        fm = flight_pattern.search(line)
        if fm:
            miles = int(fm.group(2).replace(",", ""))
            if 1000 <= miles <= max_miles:
                key = f"DL{fm.group(1)}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "flight": key,
                        "notes": line[:150],
                    })
                continue

        # Try time+miles
        tm = time_miles.search(line)
        if tm:
            miles = int(tm.group(3).replace(",", ""))
            if 1000 <= miles <= max_miles:
                key = f"{tm.group(1)}-{tm.group(2)}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "depart_time": tm.group(1),
                        "arrive_time": tm.group(2),
                        "notes": line[:150],
                    })
                continue

        # Calendar pattern
        cm = cal_pattern.search(line)
        if cm:
            miles = int(cm.group(1).replace(",", ""))
            if 1000 <= miles <= max_miles:
                key = f"cal-{miles}-{line[:30]}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "notes": f"Calendar: {line[:150]}",
                    })
                continue

    # Fallback: raw miles extraction
    if not matches:
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
                        "notes": f"Raw: {line.strip()[:150]}",
                    })
                    if len(matches) >= 5:
                        break

    return matches


def _run_hybrid(inputs: Dict[str, Any], observations: List[str]) -> Dict[str, Any]:
    """Hybrid: BrowserAgent for login, Playwright for search + extraction."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    search_url = _booking_url(origin, dest, depart_date, cabin, travelers)

    # Phase 1: BrowserAgent login (in thread to avoid asyncio loop contamination)
    observations.append("Phase 1: BrowserAgent login to Delta")
    _phase1_result = [None]

    def _phase1_worker():
        _phase1_result[0] = adaptive_run(
            goal=_login_goal(),
            url=DELTA_URL,
            max_steps=20,
            airline="delta",
            inputs=inputs,
            max_attempts=1,
            trace=True,
            use_vision=True,
        )

    _t1 = threading.Thread(target=_phase1_worker, daemon=True)
    _t1.start()
    _t1.join(timeout=600)
    login_result = _phase1_result[0] or {"ok": False, "error": "Phase 1 thread timed out"}

    if not login_result["ok"]:
        observations.append(f"Login failed: {login_result['error']}")
        # Continue anyway - Delta search works without login, just heavier
        observations.append("Continuing without login (results may be heavier)")

    login_info = login_result.get("result") or {}
    observations.append(f"Login status: {login_info.get('status', 'unknown')}")

    # Phase 2: Playwright navigation + extraction
    observations.append("Phase 2: Playwright search + extraction")
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        observations.append("Playwright not available, falling back to agent-only")
        return _run_agent_only(inputs, observations)

    matches: List[Dict[str, Any]] = []
    errors: List[str] = []
    result_text_parts: List[str] = []

    # Run sync_playwright in a separate thread to avoid asyncio loop conflicts
    def _pw_worker():
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    errors.append("No browser contexts")
                    return _run_agent_only(inputs, observations)

                context = contexts[0]

                # Always create a new page to avoid using pages closed by Phase 1
                page = context.new_page()


                # Navigate to search URL
                observations.append(f"Navigating to: {search_url}")
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    observations.append(f"Nav warning: {e}")

                # Wait for form to load
                time.sleep(5)

                # Verify Shop with Miles is enabled via JS (don't click - URL should set it)
                try:
                    miles_checked = page.evaluate("""() => {
                        const cb = document.querySelector('[id*="shopWithMiles"], input[name*="shopWithMiles"]');
                        if (cb) return cb.checked;
                        // Check for toggle state
                        const toggle = document.querySelector('[class*="shopWithMiles"]');
                        if (toggle) return toggle.classList.contains('active') || toggle.classList.contains('checked');
                        return null;
                    }""")
                    observations.append(f"Shop with Miles checked: {miles_checked}")

                    if miles_checked is False:
                        # Need to click it
                        page.evaluate("""() => {
                            const cb = document.querySelector('[id*="shopWithMiles"], input[name*="shopWithMiles"]');
                            if (cb) { cb.click(); return; }
                            const labels = Array.from(document.querySelectorAll('label, span'));
                            const match = labels.find(l => /shop.*miles/i.test(l.textContent));
                            if (match) match.click();
                        }""")
                        time.sleep(2)
                        observations.append("Clicked Shop with Miles toggle")
                except Exception as e:
                    observations.append(f"Miles toggle check error: {e}")

                # Click Find Flights
                try:
                    page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const find = btns.find(b => /find.*flight/i.test(b.textContent));
                        if (find) find.click();
                    }""")
                    observations.append("Clicked Find Flights")
                except Exception as e:
                    observations.append(f"Find Flights click error: {e}")

                # Wait for results - use longer wait since this is the heavy part
                observations.append("Waiting 25s for results to load...")
                time.sleep(25)

                # Extract data via JS (no screenshots - avoids crash)
                try:
                    data = page.evaluate(_extract_results_js())

                    observations.append(f"Page URL: {data.get('url', '?')}")
                    observations.append(f"Page title: {data.get('title', '?')}")
                    observations.append(f"Calendar entries: {len(data.get('calendar', []))}")
                    observations.append(f"Flight entries: {len(data.get('flights', []))}")
                    observations.append(f"Miles lines: {len(data.get('milesLines', []))}")
                    observations.append(f"Price elements: {len(data.get('fromPrices', []))}")

                    # Combine all text for parsing
                    for item in data.get("calendar", []):
                        result_text_parts.append(f"CALENDAR: {item}")
                    for item in data.get("flights", []):
                        result_text_parts.append(f"FLIGHT: {item}")
                    for item in data.get("milesLines", []):
                        result_text_parts.append(item)
                    for item in data.get("fromPrices", []):
                        result_text_parts.append(f"PRICE: {item}")

                except Exception as e:
                    observations.append(f"JS extraction error: {e}")
                    errors.append(f"JS extraction: {e}")

                # Try a second extraction after more time
                if not result_text_parts:
                    observations.append("First extraction empty, waiting 15s more...")
                    time.sleep(15)
                    try:
                        data = page.evaluate(_extract_results_js())
                        for item in data.get("calendar", []):
                            result_text_parts.append(f"CALENDAR: {item}")
                        for item in data.get("flights", []):
                            result_text_parts.append(f"FLIGHT: {item}")
                        for item in data.get("milesLines", []):
                            result_text_parts.append(item)
                        observations.append(f"Second extraction: {len(result_text_parts)} lines")
                    except Exception as e:
                        observations.append(f"Second extraction error: {e}")

                # Save debug screenshot (safe since we're not rendering it in agent)
                try:
                    page.screenshot(path="/tmp/delta_hybrid_results.png")
                except Exception:
                    pass

                # Clean up - close the page to free memory
                try:
                    page.close()
                except Exception:
                    pass

        except Exception as exc:
            errors.append(f"Playwright phase error: {exc}")
            observations.append(f"Playwright error: {exc}")

    _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
    _pw_thread.start()
    _pw_thread.join(timeout=300)
    if _pw_thread.is_alive():
        errors.append("Playwright phase timed out after 300s")
        observations.append("Playwright phase timed out")

    # Parse results
    combined_text = "\n".join(result_text_parts)
    if combined_text:
        matches = _parse_matches(combined_text, inputs)
        observations.append(f"Parsed {len(matches)} matches from Playwright extraction")

    book_url = _booking_url(origin, dest, depart_date, cabin, travelers)
    for m in matches:
        if "booking_url" not in m:
            m["booking_url"] = book_url

    summary_parts = [f"Delta hybrid search: {len(matches)} flight(s) found for {origin}-{dest}"]
    if matches:
        best = min(m["miles"] for m in matches)
        summary_parts.append(f"Best: {best:,} miles")

    return {
        "mode": "live",
        "real_data": True,
        "matches": matches,
        "booking_url": book_url,
        "summary": ". ".join(summary_parts) + ".",
        "raw_observations": observations,
        "errors": errors,
    }


def _run_agent_only(inputs: Dict[str, Any], observations: List[str]) -> Dict[str, Any]:
    """Fallback: pure BrowserAgent approach."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=days_ahead)
    search_url = _booking_url(origin, dest, depart_date, cabin, travelers)
    book_url = search_url

    cabin_display = CABIN_MAP.get(cabin, cabin.title())

    # Use day 5 as start so we get actual results, not just near-term sold-out
    start_date = date.today() + timedelta(days=5)
    end_date = date.today() + timedelta(days=days_ahead)
    search_url = _booking_url(origin, dest, start_date, cabin, travelers)
    goal = "\n".join([
        f"Search for Delta SkyMiles award flights {origin} to {dest}, {travelers} pax, {cabin_display}.",
        f"Scan ALL available dates from {start_date.strftime('%b %-d')} through {end_date.strftime('%b %-d, %Y')}.",
        "",
        "=== STEP 1 — VERIFY LOGIN ===",
        "Look at top-right of the page.",
        "If you see your name or miles balance → already logged in → skip to STEP 2.",
        "If you see 'Log In' → click it, use credentials for www.delta.com, wait 5.",
        "",
        "=== STEP 2 — NAVIGATE TO AWARD SEARCH ===",
        f"Navigate to: {search_url}",
        "wait 5",
        "",
        "=== STEP 3 — ENABLE SHOP WITH MILES ===",
        "Look for 'Shop with Miles' toggle/checkbox. If NOT checked/active, click it once. wait 2.",
        "",
        "=== STEP 4 — FIND FLIGHTS ===",
        "Click the 'Find Flights' button.",
        "IMPORTANT: After clicking, execute wait-30 action immediately — the results page takes 20-40 seconds to load.",
        "DO NOT give up ('done') just because the page is loading. Wait patiently.",
        "wait 30",
        "",
        "=== STEP 5 — VERIFY RESULTS LOADED (CRITICAL) ===",
        "Take a screenshot NOW.",
        "LOOK CAREFULLY at what you see:",
        "  IF you see FLIGHT RESULTS with departure times (like '9:10 AM') AND miles amounts → GOOD! Go to STEP 6.",
        "  IF you see 'page too heavy' in the snapshot OR screenshot fails:",
        "    The results page is still loading. DO NOT give up.",
        "    → execute wait-30 action again → then take screenshot → continue to STEP 6.",
        "  IF you see the SEARCH FORM (city input boxes, date picker, cabin dropdown) → NOT loaded yet.",
        "    → wait 20 more seconds → take another screenshot.",
        "    → If STILL on search form after 45 seconds total:",
        "      STOP. done. Report: 'Results page did not load. Cannot confirm availability.'",
        "  NEVER report miles values if you only see the search form.",
        "  NEVER fabricate or estimate miles amounts.",
        "",
        "=== STEP 6 — SCAN THE DATE CALENDAR ===",
        "At the top of the results there is a DATE CAROUSEL showing ~7 dates with miles prices.",
        "Each date shows a price like '499,900 mi' or '300,400 mi'.",
        "",
        "6a. Read ALL visible dates and their exact miles prices.",
        "6b. Click the RIGHT ARROW '>' or '⟩' at the right edge of the date carousel to advance.",
        "    wait 5.",
        "6c. Read ALL new dates and prices.",
        "6d. Click '>' again. wait 5. Read ALL dates and prices.",
        "6e. Click '>' again. wait 5. Read ALL dates and prices.",
        "6f. Click '>' again. wait 5. Read ALL dates and prices.",
        f"You have now scanned ~{days_ahead} days of availability.",
        "",
        "=== STEP 7 — SCREENSHOT ===",
        "Take a screenshot showing the current results.",
        "",
        "=== STEP 8 — DONE ===",
        "done",
        "Report ALL dates and prices found:",
        "DATE_STRIP: [date]: [miles] miles | [date]: [miles] miles | ...",
        "CHEAPEST: [date] — [miles] miles",
        "",
        "CRITICAL RULES:",
        "  - Only report exact prices you SAW on screen.",
        "  - Do NOT round, estimate, or make up numbers.",
        "  - If the price shows 499,900 miles, report 499,900 miles.",
        f"  - Report all dates found, even above {max_miles:,} miles.",
        "  - If no dates have award availability, report 'No award availability found in this window'.",
    ])

    _agent_result = [None]

    def _agent_worker():
        # max_attempts=1 to avoid asyncio loop contamination on retry
        # (sync_playwright leaves event loop state after first run)
        _agent_result[0] = adaptive_run(
            goal=goal,
            url=DELTA_URL,
            max_steps=60,
            airline="delta",
            inputs=inputs,
            max_attempts=1,
            trace=True,
            use_vision=True,
        )

    _t = threading.Thread(target=_agent_worker, daemon=True)
    _t.start()
    _t.join(timeout=600)
    agent_run = _agent_result[0] or {"ok": False, "error": "Agent thread timed out"}
    if agent_run["ok"]:
        run_result = agent_run.get("result") or {}
        result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)
        observations.append(f"Agent-only status: {run_result.get('status', 'unknown')}")

        live_matches = _parse_matches(result_text, inputs)
        for m in live_matches:
            if "booking_url" not in m:
                m["booking_url"] = book_url

        return {
            "mode": "live",
            "real_data": True,
            "matches": live_matches,
            "booking_url": book_url,
            "summary": f"Delta agent-only: {len(live_matches)} match(es).",
            "raw_observations": observations,
            "errors": [],
        }

    observations.append(f"Agent-only failed: {agent_run['error']}")
    return {
        "mode": "live",
        "real_data": False,
        "matches": [],
        "booking_url": book_url,
        "summary": f"Delta search failed: {agent_run['error']}",
        "raw_observations": observations,
        "errors": [agent_run["error"]],
    }


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))
    travelers = int(inputs["travelers"])
    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, cabin, travelers)

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {', '.join(destinations)}",
        f"Cabin: {cabin}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved; run would require manual auth flow.")

    if browser_agent_enabled():
        # Playwright Phase 2 is unreliable (page crashes, JS extraction fails).
        # Go straight to agent-only which uses the improved multi-date calendar goal.
        return _run_agent_only(inputs, observations)

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    matches = [{
        "route": f"{inputs['from']}-{destinations[0]}",
        "date": today.isoformat(),
        "miles": min(25000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Delta match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
