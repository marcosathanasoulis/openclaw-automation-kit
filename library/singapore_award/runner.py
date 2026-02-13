from __future__ import annotations

import os
import re
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List
from urllib.parse import urlencode

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal

SIA_URL = "https://www.singaporeair.com"
SIA_LOGIN_URL = "https://www.singaporeair.com/en_UK/us/ppsclub-krisflyer/login/"
SIA_REDEEM_URL = "https://www.singaporeair.com/en_UK/us/home#/book/redeemflight"

CABIN_MAP = {
    "business": "Business",
    "economy": "Economy",
    "first": "First",
    "premium_economy": "Premium Economy",
}

# City display names for autocomplete matching
CITY_NAMES = {
    "SFO": "San Francisco",
    "SIN": "Singapore",
    "BKK": "Bangkok",
    "NRT": "Tokyo Narita",
    "HND": "Tokyo Haneda",
    "LAX": "Los Angeles",
    "JFK": "New York",
}


def _booking_url(origin: str, dest: str, depart_date: date) -> str:
    """Construct a Singapore Airlines KrisFlyer redemption link."""
    # SIA SPA doesn't support deep search params, link to the redeem page
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


def _fill_form_and_search(
    page: Any,
    origin: str,
    dest: str,
    cabin: str,
    travelers: int,
    depart_date: date,
) -> Dict[str, Any]:
    """Fill the SIA redemption form using Playwright (hybrid approach).

    This uses explicit DOM selectors and slow typing to work with
    the Vue.js form components on singaporeair.com.
    """
    origin_name = CITY_NAMES.get(origin, origin)
    dest_name = CITY_NAMES.get(dest, dest)
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    month_display = depart_date.strftime("%B %Y")
    date_str = depart_date.strftime("%Y-%m-01")
    errors: List[str] = []

    try:
        # Wait for form to be ready
        page.wait_for_selector("form.redeem-flight", timeout=15000)
    except Exception:
        return {"ok": False, "error": "Form not found after login", "errors": ["form.redeem-flight not found"]}

    try:
        # --- Origin field ---
        origin_input = page.locator("input[name='flightOrigin']")
        origin_input.click()
        time.sleep(0.5)
        origin_input.fill("")
        origin_input.type(origin_name[:8], delay=120)  # Slow typing
        time.sleep(4)  # Wait for autocomplete
        suggest = page.locator(f".suggest-item:has-text('{origin_name}')")
        if suggest.count() > 0:
            suggest.first.click()
        else:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        time.sleep(1)

        # --- Destination field ---
        dest_input = page.locator("input[name='redeemFlightDestination']")
        dest_input.click()
        time.sleep(0.5)
        dest_input.fill("")
        dest_input.type(dest_name, delay=100)
        time.sleep(4)
        suggest = page.locator(f".suggest-item:has-text('{dest_name}')")
        if suggest.count() > 0:
            suggest.first.click()
        else:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        page.keyboard.press("Escape")
        time.sleep(2)

        # --- Class dropdown (readonly, must use suggest-item click) ---
        class_input = page.locator("[name=flightClass]")
        class_input.click()
        time.sleep(2)
        class_suggest = page.locator(f".suggest-item:has-text('{cabin_display}')")
        if class_suggest.count() > 0:
            class_suggest.first.click()
        else:
            errors.append(f"Class suggestion '{cabin_display}' not found")
        time.sleep(1)

        # --- Passengers ---
        if travelers > 1:
            pax_input = page.locator("[name=flightPassengers]")
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

        # Check one-way
        oneway_label = page.locator(".calendar-root label[for='oneway_id']")
        if oneway_label.count() > 0:
            oneway_label.first.click()
            time.sleep(1)

        # Select month from dropdown
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

        # Click day 1 of the month
        day_cell = page.locator(f".calendar_days li[date-data='{date_str}']")
        if day_cell.count() > 0:
            day_cell.first.click()
            time.sleep(1)
        else:
            errors.append(f"Day cell for {date_str} not found")

        # Click Done
        done_btn = page.locator(".calendar-root .btn-primary:not([disabled])")
        if done_btn.count() > 0:
            done_btn.first.click()
            time.sleep(2)

        # --- Click Search ---
        time.sleep(5)  # Extra pause before search to avoid Akamai
        search_btn = page.locator("form.redeem-flight button[type='submit']")
        if search_btn.count() > 0:
            search_btn.first.click()
        else:
            errors.append("Search button not found, trying fallback")
            page.evaluate("document.querySelector('form.redeem-flight').submit()")
        time.sleep(15)  # Wait for results

        return {"ok": True, "errors": errors}

    except Exception as exc:
        errors.append(str(exc))
        return {"ok": False, "error": str(exc), "errors": errors}


def _scrape_results(page: Any, target_month: int, target_year: int) -> List[Dict[str, Any]]:
    """Scrape 7-day calendar results using Playwright."""
    results: List[Dict[str, Any]] = []

    try:
        # Check for error messages
        error_el = page.locator(".error-message, .no-results")
        if error_el.count() > 0:
            return []

        # Navigate left 4 times to start of month
        left_arrows = page.locator(".SevenDayCalendar a, .SevenDayCalendar button")
        if left_arrows.count() >= 2:
            for _ in range(4):
                left_arrows.first.click()
                time.sleep(2)

        # Sweep right through the month (7 passes for ~5 weeks)
        for _ in range(7):
            cells = page.locator(".viewcell")
            for i in range(cells.count()):
                cell = cells.nth(i)
                date_el = cell.locator(".date")
                miles_el = cell.locator(".milesvalue")
                if date_el.count() > 0 and miles_el.count() > 0:
                    date_text = date_el.inner_text().strip()
                    miles_text = miles_el.inner_text().strip()
                    if miles_text and miles_text != "-":
                        results.append({
                            "date_text": date_text,
                            "miles_text": miles_text,
                        })

            # Navigate right
            if left_arrows.count() >= 2:
                left_arrows.last.click()
                time.sleep(2)

    except Exception:
        pass  # Best-effort scraping

    # Deduplicate and parse
    seen = set()
    parsed: List[Dict[str, Any]] = []
    for r in results:
        key = f"{r['date_text']}|{r['miles_text']}"
        if key in seen:
            continue
        seen.add(key)

        # Parse miles from text like "148,000" or "148K"
        miles_match = re.search(r"([\d,]+(?:\.\d+)?)\s*[Kk]?", r["miles_text"].replace(",", ""))
        miles = 0
        if miles_match:
            val = float(miles_match.group(1))
            if val < 1000:
                miles = int(val * 1000)
            else:
                miles = int(val)

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
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=days_ahead)

    # Phase 1: BrowserAgent login (short goal, ~20 steps max)
    observations.append("Phase 1: BrowserAgent login")
    login_result = run_browser_agent_goal(
        goal=_login_goal(),
        url=SIA_LOGIN_URL,
        max_steps=20,
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
        observations.append("Playwright not available — falling back to agent-only mode")
        return _run_agent_only(inputs, observations)

    matches: List[Dict[str, Any]] = []
    errors: List[str] = []

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
            # Find SIA page or create one
            page = None
            for p_page in context.pages:
                if "singaporeair" in p_page.url:
                    page = p_page
                    break

            if page is None:
                page = context.new_page()
                page.goto(SIA_REDEEM_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
            elif "redeemflight" not in page.url:
                page.goto(SIA_REDEEM_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)

            observations.append(f"Playwright connected, page URL: {page.url}")

            # Fill form and search
            form_result = _fill_form_and_search(
                page, origin, dest, cabin, travelers, depart_date,
            )
            if form_result.get("errors"):
                errors.extend(form_result["errors"])

            if form_result["ok"]:
                observations.append("Form filled and search submitted")

                # Phase 3: Scrape results
                observations.append("Phase 3: Scraping results")
                raw_results = _scrape_results(page, depart_date.month, depart_date.year)
                observations.append(f"Scraped {len(raw_results)} date entries")

                book_url = _booking_url(origin, dest, depart_date)
                per_person_max = max_miles // travelers
                for r in raw_results:
                    if r["miles"] > 0 and r["miles"] <= per_person_max:
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

                observations.append(f"Found {len(matches)} matches under {max_miles:,} miles")
            else:
                observations.append(f"Form fill failed: {form_result.get('error', 'unknown')}")

    except Exception as exc:
        errors.append(f"Playwright phase error: {exc}")
        observations.append(f"Playwright error: {exc}")

    book_url_final = _booking_url(origin, dest, depart_date)
    return {
        "mode": "live",
        "real_data": True,
        "matches": matches,
        "booking_url": book_url_final,
        "summary": (
            f"SIA hybrid search completed. "
            f"Found {len(matches)} flights under {max_miles:,} miles for {origin}-{dest}."
        ),
        "raw_observations": observations,
        "errors": errors,
    }


def _run_agent_only(inputs: Dict[str, Any], observations: List[str]) -> Dict[str, Any]:
    """Fallback: agent-only approach (original behavior)."""
    agent_run = run_browser_agent_goal(
        goal=_goal(inputs),
        url=SIA_URL,
        max_steps=60,
        trace=True,
        use_vision=True,
    )
    if agent_run["ok"]:
        run_result = agent_run.get("result") or {}
        observations.extend([
            "BrowserAgent run executed (agent-only mode).",
            f"BrowserAgent status: {run_result.get('status', 'unknown')}",
            f"BrowserAgent steps: {run_result.get('steps', 'n/a')}",
            f"BrowserAgent trace_dir: {run_result.get('trace_dir', 'n/a')}",
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


def _goal(inputs: Dict[str, Any]) -> str:
    """Build goal for agent-only fallback mode."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_MAP.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)
    month_display = depart_date.strftime("%B %Y")
    travelers = int(inputs["travelers"])
    max_miles = int(inputs["max_miles"])

    lines = [
        f"Search for Singapore Airlines KrisFlyer award flights {origin} to {dest} "
        f"around {month_display}, {cabin_display} class.",
        "",
        "STEP 1 - LOGIN:",
        "Login with KrisFlyer number: 8814147288.",
        "Get password from keychain for www.singaporeair.com.",
        "If already logged in, skip login.",
        "",
        "STEP 2 - NAVIGATE TO REDEMPTION SEARCH:",
        "Click 'Redeem flights' or navigate to the redemption form.",
        "",
        "STEP 3 - FILL FORM AND SEARCH:",
        f"Set origin to {origin}, destination to {dest}.",
        f"Set cabin to {cabin_display}, passengers to {travelers}.",
        f"Set date to {depart_date.isoformat()}.",
        "Click Search.",
        "",
        "STEP 4 - READ RESULTS:",
        f"Report available flights under {max_miles:,} miles ({max_miles // travelers:,} per person).",
        "Before calling done, note the current page URL from your browser.",
        "Use the done action with your findings.",
    ]
    return "\n".join(lines)


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
    book_url = _booking_url(inputs["from"], destinations[0], depart_date)

    if browser_agent_enabled():
        # Use hybrid approach: BrowserAgent login + Playwright form fill
        return _run_hybrid(inputs, observations)

    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    matches = [
        {
            "route": f"{inputs['from']}-{destinations[0]}",
            "date": today.isoformat(),
            "miles": min(70000, max_miles),
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
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic Singapore match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
