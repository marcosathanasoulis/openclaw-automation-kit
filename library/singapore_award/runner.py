from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal
from openclaw_automation.adaptive import adaptive_run

SIA_URL = "https://www.singaporeair.com"
SIA_LOGIN_URL = "https://www.singaporeair.com/en_UK/us/ppsclub-krisflyer/login/"
SIA_REDEEM_URL = "https://www.singaporeair.com/en_UK/us/home#/book/redeemflight"

CABIN_MAP = {
    "business": "Business",
    "economy": "Economy",
    "first": "First",
    "premium_economy": "Premium Economy",
}

CITY_NAMES = {
    "SFO": "San Francisco",
    "SIN": "Singapore",
    "BKK": "Bangkok",
    "NRT": "Tokyo Narita",
    "HND": "Tokyo Haneda",
    "LAX": "Los Angeles",
    "JFK": "New York",
    "LHR": "London",
    "CDG": "Paris",
    "FRA": "Frankfurt",
    "ICN": "Seoul",
    "HKG": "Hong Kong",
    "TPE": "Taipei",
}


def _booking_url(origin: str, dest: str, depart_date: date) -> str:
    return SIA_REDEEM_URL


def _login_goal() -> str:
    return "\n".join([
        "Login to Singapore Airlines KrisFlyer.",
        "",
        "1. Go to the login page if not already there.",
        "2. KrisFlyer number: 8814147288",
        "3. Get password from keychain for www.singaporeair.com.",
        "4. Enter credentials and click login.",
        "5. If already logged in (you see a name or welcome message), report done immediately.",
        "6. After successful login, navigate to: "
        "https://www.singaporeair.com/en_UK/us/home#/book/redeemflight",
        "7. Use the done action when you see the redemption search form.",
    ])


def _click_suggest_item(page: Any, text: str, timeout: int = 5000) -> bool:
    """Click a suggest-item containing the given text."""
    try:
        suggest = page.locator(f".suggest-item:has-text('{text}')")
        suggest.first.wait_for(state="visible", timeout=timeout)
        suggest.first.click()
        return True
    except Exception:
        return False


def _fill_form_and_search(
    page: Any,
    origin: str,
    dest: str,
    cabin: str,
    travelers: int,
    depart_date: date,
) -> Dict[str, Any]:
    """Fill the SIA redemption form using Playwright (hybrid approach)."""
    origin_name = CITY_NAMES.get(origin, origin)
    dest_name = CITY_NAMES.get(dest, dest)
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    month_display = depart_date.strftime("%B %Y")
    date_str = depart_date.strftime("%Y-%m-%d")
    errors: List[str] = []

    try:
        page.wait_for_selector("form.redeem-flight", timeout=15000)
    except Exception:
        return {"ok": False, "error": "Form not found after login", "errors": ["form.redeem-flight not found"]}

    # Dismiss cookie popup
    try:
        page.evaluate("""() => {
            let btn = document.querySelector('button.dwc--SiaCookie__PopupClose, button:has-text("ACCEPT"), .cookie-accept-btn');
            if (btn) btn.click();
            let overlay = document.querySelector('.dwc--SiaCookie__Popup, .cookie-overlay, .cookie-banner');
            if (overlay) overlay.remove();
        }""")
        time.sleep(1)
    except Exception:
        pass

    try:
        accept_btn = page.locator("text=ACCEPT").first
        if accept_btn.is_visible(timeout=2000):
            accept_btn.click(timeout=3000)
            time.sleep(1)
    except Exception:
        pass

    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass

    try:
        # --- Origin field ---
        origin_input = page.locator("input[name='flightOrigin']")
        current_origin = origin_input.input_value(timeout=10000)
        if origin.upper() not in current_origin.upper():
            origin_input.click()
            time.sleep(0.5)
            origin_input.click(click_count=3)
            time.sleep(0.3)
            origin_input.type(origin_name[:8], delay=120)
            time.sleep(3)
            if not _click_suggest_item(page, origin_name):
                page.keyboard.press("ArrowDown")
                time.sleep(0.3)
                page.keyboard.press("Enter")
            time.sleep(1)

        page.keyboard.press("Escape")
        time.sleep(0.5)

        # --- Destination field ---
        dest_input = page.locator("input[name='redeemFlightDestination']")
        dest_input.click(timeout=10000)
        time.sleep(0.5)
        dest_input.click(click_count=3)
        time.sleep(0.3)
        dest_input.type(dest_name, delay=100)
        time.sleep(4)
        if not _click_suggest_item(page, dest_name):
            page.keyboard.press("ArrowDown")
            time.sleep(0.3)
            page.keyboard.press("Enter")
        page.keyboard.press("Escape")
        time.sleep(2)

        # --- Class dropdown ---
        class_input = page.locator("input[name='flightClass']")
        current_class = class_input.input_value()
        if cabin_display.lower() not in current_class.lower():
            class_input.click()
            time.sleep(2)
            if not _click_suggest_item(page, cabin_display):
                errors.append(f"Class suggestion '{cabin_display}' not found")
            time.sleep(1)

        # --- Passengers ---
        if travelers > 1:
            pax_input = page.locator("input[name='flightPassengers']")
            pax_input.click()
            time.sleep(1)
            for _ in range(travelers - 1):
                add_btn = page.locator("button[aria-label='Add Adult Count']")
                if add_btn.count() > 0:
                    add_btn.first.click()
                    time.sleep(0.5)
            page.keyboard.press("Escape")
            time.sleep(1)

        # --- Calendar / Date ---
        date_input = page.locator("input[name='departDate']")
        date_input.click()
        time.sleep(2)

        oneway_label = page.locator(".calendar-root label[for='oneway_id']")
        if oneway_label.count() > 0:
            oneway_label.first.click()
            time.sleep(1)

        month_input = page.locator(".calendar-root .vue-simple-suggest input")
        if month_input.count() > 0:
            month_input.first.click()
            time.sleep(1)
            month_suggest = page.locator(f".suggest-item:has-text('{month_display}')")
            if month_suggest.count() > 0:
                month_suggest.first.click()
                time.sleep(1)
            else:
                errors.append(f"Month '{month_display}' not found in calendar dropdown")

        day_cell = page.locator(f".calendar_days li[date-data='{date_str}']")
        if day_cell.count() > 0:
            day_cell.first.click()
            time.sleep(1)
        else:
            avail_days = page.locator(".calendar_days li:not(.disabled):not(.past)")
            if avail_days.count() > 0:
                avail_days.nth(min(6, avail_days.count() - 1)).click()
                time.sleep(1)
                errors.append(f"Day cell for {date_str} not found, clicked alternate date")
            else:
                errors.append("No available day cells found in calendar")

        done_btn = page.locator(".calendar-root .btn-primary:not([disabled])")
        if done_btn.count() > 0:
            done_btn.first.click()
            time.sleep(2)

        # --- Click Search ---
        time.sleep(3)
        search_btn = page.locator("form.redeem-flight button[type='submit']")
        if search_btn.count() > 0:
            search_btn.first.click()
        else:
            errors.append("Search button not found")
            return {"ok": False, "error": "Search button not found", "errors": errors}

        time.sleep(15)

        try:
            page.screenshot(path="/tmp/sia_after_search.png")
        except Exception:
            pass

        return {"ok": True, "errors": errors}

    except Exception as exc:
        errors.append(str(exc))
        try:
            page.screenshot(path="/tmp/sia_error.png")
        except Exception:
            pass
        return {"ok": False, "error": str(exc), "errors": errors}


def _scrape_results(page: Any, target_month: int, target_year: int) -> List[Dict[str, Any]]:
    """Scrape 7-day calendar and flight results using Playwright."""
    results: List[Dict[str, Any]] = []

    def _extract_via_js():
        try:
            js = """() => {
                let cells = document.querySelectorAll('.viewcell:not(.loading)');
                let data = [];
                cells.forEach(c => {
                    let dateEl = c.querySelector('.date');
                    let milesEl = c.querySelector('.milesvalue');
                    if (dateEl && milesEl) {
                        let d = dateEl.textContent.trim();
                        let m = milesEl.textContent.trim();
                        if (m && m !== '-' && m !== '--') {
                            data.push({date_text: d, miles_text: m});
                        }
                    }
                });
                let flights = document.querySelectorAll('.FlightDisplay');
                flights.forEach(f => {
                    let text = f.textContent.trim();
                    let mMatch = text.match(/(\\d[\\d,]+)\\s*miles/);
                    if (mMatch) {
                        data.push({
                            date_text: 'flight',
                            miles_text: mMatch[1],
                            info: text.substring(0, 150),
                        });
                    }
                });
                return JSON.stringify(data);
            }"""
            raw = page.evaluate(js)
            return json.loads(raw) if raw else []
        except Exception:
            return []

    try:
        try:
            page.locator(".viewcell:not(.loading)").first.wait_for(
                state="visible", timeout=15000
            )
        except Exception:
            pass
        time.sleep(3)

        results.extend(_extract_via_js())

        right_btn = page.locator(".SevenDayCalendar button.flip.right")
        left_btn = page.locator(".SevenDayCalendar button.flip.left")

        if left_btn.count() > 0:
            for _ in range(3):
                try:
                    left_btn.first.click()
                    time.sleep(3)
                    results.extend(_extract_via_js())
                except Exception:
                    break

        if right_btn.count() > 0:
            for _ in range(7):
                try:
                    right_btn.first.click()
                    time.sleep(3)
                    results.extend(_extract_via_js())
                except Exception:
                    break

    except Exception:
        pass

    # Fallback: parse entire results section text
    if not results:
        try:
            section = page.locator(".FlightSelections, .SevenDayCalendar")
            if section.count() > 0:
                text = section.first.inner_text()
                day_pattern = re.compile(
                    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
                    r'.*?(\d[\d,]+)\s*miles',
                    re.DOTALL | re.IGNORECASE
                )
                for m in day_pattern.finditer(text):
                    date_match = re.search(
                        r'((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+\w+)',
                        m.group(0)
                    )
                    if date_match:
                        results.append({
                            "date_text": date_match.group(1),
                            "miles_text": m.group(1),
                        })
        except Exception:
            pass

    # Deduplicate and parse
    seen = set()
    parsed: List[Dict[str, Any]] = []
    for r in results:
        key = f"{r['date_text']}|{r['miles_text']}"
        if key in seen:
            continue
        seen.add(key)

        miles_str = r["miles_text"].replace(",", "")
        miles_match = re.search(r"(\d+)", miles_str)
        miles = 0
        if miles_match:
            val = int(miles_match.group(1))
            miles = val * 1000 if val < 1000 else val

        parsed.append({
            "date": r["date_text"],
            "miles": miles,
            "raw": r["miles_text"],
        })

    return parsed


def _run_hybrid(inputs: Dict[str, Any], observations: List[str]) -> Dict[str, Any]:
    """Hybrid approach: BrowserAgent for login, Playwright for form + scraping."""
    origin = inputs["from"]
    destinations = inputs["to"]
    dest = destinations[0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    days_ahead = int(inputs["days_ahead"])
    mid_days = days_ahead
    depart_date = date.today() + timedelta(days=mid_days)

    # Phase 1: BrowserAgent login
    observations.append("Phase 1: BrowserAgent login")
    login_result = adaptive_run(
        goal=_login_goal(),
        url=SIA_LOGIN_URL,
        max_steps=20,
        airline="singapore",
        inputs=inputs,
        max_attempts=1,
        trace=True,
        use_vision=True,
    )

    if not login_result["ok"]:
        observations.append(f"Login failed: {login_result['error']}")
        return {
            "mode": "live",
            "real_data": False,
            "matches": [],
            "summary": f"SIA login failed: {login_result['error']}",
            "raw_observations": observations,
            "errors": [login_result["error"]],
        }

    login_info = login_result.get("result") or {}
    observations.append(f"Login status: {login_info.get('status', 'unknown')}")
    observations.append(f"Login steps: {login_info.get('steps', 'n/a')}")

    # Phase 2: Playwright form fill
    observations.append("Phase 2: Playwright form fill (hybrid)")
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        observations.append("Playwright not available")
        return _run_agent_only(inputs, observations)

    matches: List[Dict[str, Any]] = []
    errors: List[str] = []

    # Run sync_playwright in a separate thread to avoid asyncio loop conflicts
    def _pw_worker():
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    errors.append("No browser contexts found after login")
                    return {
                        "mode": "live",
                        "real_data": False,
                        "matches": [],
                        "summary": "No browser context available after BrowserAgent login",
                        "raw_observations": observations,
                        "errors": errors,
                    }

                context = contexts[0]
                page = None
                for p_page in context.pages:
                    if "singaporeair" in p_page.url:
                        page = p_page
                        break

                if page is None:
                    page = context.new_page()

                # Two-step navigation: homepage first (loads Angular), then redeem hash
                homepage = "https://www.singaporeair.com/en_UK/us/home"
                page.goto(homepage, wait_until="domcontentloaded", timeout=30000)
                time.sleep(6)
                page.goto(SIA_REDEEM_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)

                observations.append(f"Playwright connected, page URL: {page.url}")

                form_result = _fill_form_and_search(
                    page, origin, dest, cabin, travelers, depart_date,
                )
                if form_result.get("errors"):
                    errors.extend(form_result["errors"])
                    for e in form_result["errors"]:
                        observations.append(f"Form note: {e}")

                if form_result["ok"]:
                    observations.append("Form filled and search submitted")

                    # Phase 3: Scrape results
                    observations.append("Phase 3: Scraping results")
                    raw_results = _scrape_results(page, depart_date.month, depart_date.year)
                    observations.append(f"Scraped {len(raw_results)} date entries")

                    book_url = _booking_url(origin, dest, depart_date)
                    for r in raw_results:
                        if r["miles"] > 0:
                            matches.append({
                                "route": f"{origin}-{dest}",
                                "date": r["date"],
                                "miles": r["miles"],
                                "travelers": travelers,
                                "cabin": cabin,
                                "mixed_cabin": False,
                                "booking_url": book_url,
                                "notes": f"raw: {r['raw']}",
                            })

                    observations.append(f"Found {len(matches)} date entries with availability")
                else:
                    observations.append(f"Form fill failed: {form_result.get('error', 'unknown')}")

        except Exception as exc:
            errors.append(f"Playwright phase error: {exc}")
            observations.append(f"Playwright error: {exc}")

    _pw_thread = threading.Thread(target=_pw_worker, daemon=True)
    _pw_thread.start()
    _pw_thread.join(timeout=300)
    if _pw_thread.is_alive():
        errors.append("Playwright phase timed out after 300s")
        observations.append("Playwright phase timed out")

    book_url_final = _booking_url(origin, dest, depart_date)
    summary_parts = [f"SIA hybrid search: {len(matches)} flights found for {origin}-{dest}"]
    if matches:
        best = min(m["miles"] for m in matches)
        summary_parts.append(f"Best: {best:,} miles")
    return {
        "mode": "live",
        "real_data": True,
        "matches": matches,
        "booking_url": book_url_final,
        "summary": ". ".join(summary_parts) + ".",
        "raw_observations": observations,
        "errors": errors,
    }


def _run_agent_only(inputs: Dict[str, Any], observations: List[str]) -> Dict[str, Any]:
    """Fallback: agent-only approach."""
    _agent_result = [None]

    def _agent_worker():
        _agent_result[0] = run_browser_agent_goal(
            goal=_goal(inputs),
            url=SIA_URL,
            max_steps=60,
            trace=True,
            use_vision=True,
        )

    _t = threading.Thread(target=_agent_worker, daemon=True)
    _t.start()
    _t.join(timeout=600)
    agent_run = _agent_result[0] or {"ok": False, "error": "Agent thread timed out"}
    if agent_run["ok"]:
        run_result = agent_run.get("result") or {}
        observations.extend([
            "BrowserAgent run executed (agent-only mode).",
            f"BrowserAgent status: {run_result.get('status', 'unknown')}",
        ])
        return {
            "mode": "live",
            "real_data": True,
            "matches": run_result.get("matches", []),
            "summary": "BrowserAgent run completed for Singapore award search (agent-only fallback).",
            "raw_observations": observations,
            "errors": [],
        }
    observations.append(f"BrowserAgent adapter error: {agent_run['error']}")
    return {
        "mode": "live",
        "real_data": False,
        "matches": [],
        "summary": f"SIA agent-only fallback failed: {agent_run['error']}",
        "raw_observations": observations,
        "errors": [agent_run["error"]],
    }


def _goal(inputs):
    """Build goal for agent-only fallback mode."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)
    travelers = int(inputs["travelers"])
    max_miles = int(inputs["max_miles"])

    origin_name = CITY_NAMES.get(origin, origin)
    dest_name = CITY_NAMES.get(dest, dest)

    lines = [
        f"Search for Singapore Airlines KrisFlyer award flights {origin} to {dest}, "
        f"{cabin_display} class, {travelers} adults, on {depart_date.strftime('%B %-d, %Y')}.",
        "",
        "=== ACTION SEQUENCE (follow EXACTLY) ===",
        "",
        "STEP 1 - LOGIN:",
        "Navigate to https://www.singaporeair.com/en_UK/us/ppsclub-krisflyer/login/",
        "KrisFlyer number: 8814147288",
        "Get password from keychain for www.singaporeair.com.",
        "Enter credentials and click login.",
        "If already logged in, skip to STEP 2.",
        "",
        "STEP 2 - NAVIGATE TO REDEEM FLIGHTS:",
        "Navigate to https://www.singaporeair.com/en_UK/us/home#/book/redeemflight",
        "Wait 5 seconds for the form to load.",
        "",
        "STEP 3 - FILL ORIGIN:",
        f"Click the origin/departure field and type '{origin_name}' or '{origin}'.",
        "Select the matching airport from suggestions.",
        "",
        "STEP 4 - FILL DESTINATION:",
        f"Click the destination field and type '{dest_name}' or '{dest}'.",
        "Select the matching airport from suggestions.",
        "",
        "STEP 5 - SET DATE:",
        f"Click the date field and navigate to {depart_date.strftime('%B %Y')}.",
        f"Select day {depart_date.day}.",
        "Use forward arrows to navigate months.",
        "",
        "STEP 6 - SET CABIN:",
        f"Set cabin class to {cabin_display} if not already set.",
        "",
        "STEP 7 - SET PASSENGERS:",
        f"Set passengers to {travelers} adults.",
        "",
        "STEP 8 - SEARCH:",
        "Click the Search button.",
        "wait 10",
        "",
        "STEP 9 - SCREENSHOT AND REPORT:",
        "screenshot",
        "Then: done",
        "Report ALL visible availability with miles costs.",
        "Format: DATE: [date] | [miles] miles | [cabin]",
        f"Focus on results under {max_miles:,} miles.",
        "",
        "=== CRITICAL NOTES ===",
        "- SIA uses Angular/Vue.js -- wait for dropdowns to appear",
        "- If cookie popup appears, dismiss it first",
        "- The form may have autocomplete dropdowns -- wait and click the right option",
        "- Do NOT use form.submit() or fetch() -- they trigger CAPTCHA",
        "- Only click real buttons",
    ]
    return "\n".join(lines)



def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    max_miles = int(inputs["max_miles"])
    cabin = str(inputs.get("cabin", "economy"))

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {', '.join(destinations)}",
        f"Cabin: {cabin}",
    ]

    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    travelers = int(inputs["travelers"])
    book_url = _booking_url(inputs["from"], destinations[0], depart_date)

    if browser_agent_enabled():
        # Try hybrid first, fall back to agent-only if it fails
        result = _run_hybrid(inputs, observations)
        if result.get("errors") or not result.get("matches"):
            observations.append("Hybrid approach failed or returned no matches, trying agent-only")
            return _run_agent_only(inputs, observations)
        return result

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    matches = [{
        "route": f"{inputs['from']}-{destinations[0]}",
        "date": today.isoformat(),
        "miles": min(70000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Singapore match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }