from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal
from openclaw_automation.adaptive import adaptive_run
from openclaw_automation.result_extract import extract_award_matches_from_text

UNITED_URL = "https://www.united.com/en/us"


def _booking_url(
    origin: str, dest: str, depart_date: date, cabin: str, travelers: int, award: bool = False,
) -> str:
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


def _login_goal() -> str:
    return "\n".join([
        "Login to United MileagePlus account.",
        "",
        "1. Look at the page. If you see 'Hi [name]' or a greeting, you are logged in. Report done.",
        "2. If NOT logged in:",
        "   a. Click 'Sign in'.",
        "   b. credentials for www.united.com",
        "   c. Type MileagePlus number ka388724.",
        "   d. Click 'Continue'.",
        "   e. wait 5",
        "   f. Type the password.",
        "   g. Click 'Sign in'.",
        "   h. wait 8",
        "   i. If SMS 2FA requested: read_sms_code (sender 26266). Enter code and submit.",
        "   j. wait 8",
        "   k. IMPORTANT: Look for a 'Remember this device' or 'Trust this device' checkbox.",
        "      If visible, CHECK it before anything else. This avoids future 2FA prompts.",
        "   l. Close any popups ('No thanks', 'Maybe later', X buttons).",
        "   m. wait 3",
        "3. After login, report done.",
        "4. If login fails after ONE attempt, report done (search proceeds without login).",
        "   Do NOT retry if you already consumed a 2FA code.",
    ])


def _extract_results_js():
    """JS to extract United flight results."""
    return """() => {
        const results = [];

        // Get all flight card text
        const cards = document.querySelectorAll(
            '[class*="flight-card"], [class*="FlightCard"], ' +
            '[class*="trip-card"], [class*="TripCard"], ' +
            '[class*="flight-info"], [class*="FlightInfo"], ' +
            '.bound-content, [data-testid*="flight"]'
        );
        cards.forEach(c => {
            const text = c.textContent.trim().replace(/\\s+/g, ' ');
            if (text.length > 10 && text.length < 500) {
                results.push({type: 'flight', text: text});
            }
        });

        // Get all text lines with prices
        const bodyText = document.body.innerText || '';
        const lines = bodyText.split('\\n');
        const priceLines = [];
        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.length > 3 && trimmed.length < 200) {
                if (/mile|\\$\\d|award|from/i.test(trimmed)) {
                    priceLines.push(trimmed);
                }
            }
        }

        // Get pricing toggle state
        const moneyTab = document.querySelector('[class*="money-miles"], [aria-label*="Money + Miles"]');
        const selectedTab = document.querySelector('[class*="selected"][class*="price"], [aria-selected="true"][class*="price"]');

        return {
            flights: results.map(r => r.text).slice(0, 15),
            priceLines: priceLines.slice(0, 30),
            url: window.location.href,
            title: document.title,
            toggleState: selectedTab ? selectedTab.textContent.trim() : 'unknown',
        };
    }"""


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse United results - handles both miles and cash prices."""
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

    # Pattern: miles
    miles_pattern = re.compile(
        r'(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?([\d,]+)\s*(?:miles|mi)',
        re.IGNORECASE,
    )

    # Pattern: cash prices
    cash_pattern = re.compile(
        r'(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)'
        r'.*?\$([\d,]+)',
        re.IGNORECASE,
    )

    # Pattern: simple miles mention
    simple_miles = re.compile(r'([\d,]+)\s*(?:miles|mi)\b', re.IGNORECASE)

    # Pattern: flight with dollar price (UA 1234 ... $912)
    flight_cash = re.compile(r'(?:UA\s*)(\d{1,5}).*?\$([\d,]+)', re.IGNORECASE)

    for line in result_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try miles pattern
        mm = miles_pattern.search(line)
        if mm:
            miles = int(mm.group(3).replace(",", ""))
            if 1000 <= miles <= max_miles:
                key = f"{mm.group(1)}-{mm.group(2)}-{miles}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": miles,
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "depart_time": mm.group(1).strip(),
                        "arrive_time": mm.group(2).strip(),
                        "notes": line[:150],
                    })
            continue

        # Try cash pattern
        cm = cash_pattern.search(line)
        if cm:
            price = int(cm.group(3).replace(",", ""))
            if price > 50:
                key = f"{cm.group(1)}-{cm.group(2)}-${price}"
                if key not in seen:
                    seen.add(key)
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": 0,
                        "cash_price": price,
                        "currency": "USD",
                        "travelers": travelers,
                        "cabin": cabin,
                        "mixed_cabin": False,
                        "depart_time": cm.group(1).strip(),
                        "arrive_time": cm.group(2).strip(),
                        "notes": line[:150],
                    })

    # Fallback: simple miles extraction
    if not [m for m in matches if m.get("miles", 0) > 0]:
        for line in result_text.split("\n"):
            sm = simple_miles.search(line)
            if sm:
                miles = int(sm.group(1).replace(",", ""))
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

    # Fallback: cash prices from agent text
    if not matches:
        for line in result_text.split("\n"):
            fc = flight_cash.search(line)
            if fc:
                price = int(fc.group(2).replace(",", ""))
                if price > 50:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": 0,
                        "cash_price": price,
                        "currency": "USD",
                        "travelers": travelers,
                        "cabin": cabin,
                        "flight": f"UA{fc.group(1)}",
                        "notes": line.strip()[:150],
                    })

    # Last fallback: any $ prices
    if not matches:
        dollar = re.compile(r'\$([\d,]+)')
        for line in result_text.split("\n"):
            dm = dollar.search(line)
            if dm and ("flight" in line.lower() or ":" in line):
                price = int(dm.group(1).replace(",", ""))
                if price > 100:
                    matches.append({
                        "route": f"{origin}-{dest}",
                        "date": depart_date.isoformat(),
                        "miles": 0,
                        "cash_price": price,
                        "currency": "USD",
                        "travelers": travelers,
                        "cabin": cabin,
                        "notes": line.strip()[:150],
                    })
                    if len(matches) >= 3:
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

    cash_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=False)

    # Phase 1: BrowserAgent login
    observations.append("Phase 1: BrowserAgent login to United")
    login_result = adaptive_run(
        goal=_login_goal(),
        url=UNITED_URL,
        max_steps=25,
        airline="united",
        inputs=inputs,
        max_attempts=1,
        trace=True,
        use_vision=True,
    )

    login_info = login_result.get("result") or {}
    login_ok = login_result.get("ok", False)
    observations.append(f"Login {'succeeded' if login_ok else 'failed'}: {login_info.get('status', 'unknown')}")

    # Phase 2: Playwright search + extraction
    observations.append("Phase 2: Playwright search + extraction")
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        observations.append("Playwright not available")
        return _run_agent_only(inputs, observations)

    matches: List[Dict[str, Any]] = []
    errors: List[str] = []
    result_text_parts: List[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            contexts = browser.contexts
            if not contexts:
                return _run_agent_only(inputs, observations)

            context = contexts[0]
            page = None
            for pg in context.pages:
                if "united.com" in pg.url:
                    page = pg
                    break
            if page is None:
                page = context.new_page()

            # Navigate to cash search URL
            observations.append(f"Navigating to: {cash_url}")
            try:
                page.goto(cash_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                observations.append(f"Nav warning: {e}")

            time.sleep(15)

            # Try to click Money + Miles tab via JS
            try:
                toggle_result = page.evaluate("""() => {
                    // Look for Money + Miles tab/link
                    const tabs = Array.from(document.querySelectorAll('button, a, [role="tab"]'));
                    const mmTab = tabs.find(t => /money.*miles/i.test(t.textContent));
                    if (mmTab) {
                        mmTab.click();
                        return 'clicked Money + Miles';
                    }
                    return 'tab not found';
                }""")
                observations.append(f"Miles toggle: {toggle_result}")
                if "clicked" in toggle_result:
                    time.sleep(10)
            except Exception as e:
                observations.append(f"Miles toggle error: {e}")

            # Extract results
            try:
                data = page.evaluate(_extract_results_js())
                observations.append(f"Flights: {len(data.get('flights', []))}")
                observations.append(f"Price lines: {len(data.get('priceLines', []))}")
                observations.append(f"Toggle state: {data.get('toggleState', '?')}")

                for item in data.get("flights", []):
                    result_text_parts.append(f"FLIGHT: {item}")
                for item in data.get("priceLines", []):
                    result_text_parts.append(item)
            except Exception as e:
                observations.append(f"Extraction error: {e}")

            # Save screenshot
            try:
                page.screenshot(path="/tmp/united_hybrid_results.png")
            except Exception:
                pass

            try:
                page.close()
            except Exception:
                pass

    except Exception as exc:
        errors.append(f"Playwright error: {exc}")
        observations.append(f"Playwright error: {exc}")

    # Parse results
    combined_text = "\n".join(result_text_parts)
    if combined_text:
        matches = _parse_matches(combined_text, inputs)
        observations.append(f"Parsed {len(matches)} matches")

    book_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)
    for m in matches:
        if "booking_url" not in m:
            m["booking_url"] = book_url

    miles_matches = [m for m in matches if m.get("miles", 0) > 0]
    cash_matches = [m for m in matches if m.get("cash_price")]

    summary_parts = [f"United hybrid search: {len(matches)} flight(s) found for {origin}-{dest}"]
    if miles_matches:
        best = min(m["miles"] for m in miles_matches)
        summary_parts.append(f"Best: {best:,} miles")
    elif cash_matches:
        best_cash = min(m["cash_price"] for m in cash_matches)
        summary_parts.append(f"Cheapest: ${best_cash:,} (cash only, miles unavailable)")

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
    cash_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=False)
    book_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)

    goal = "\n".join([
        f"Search for United award flights {origin} to {dest}, "
        f"{travelers} adult(s), {cabin} class, {depart_date.strftime('%B %-d, %Y')}.",
        "",
        "STEP 1 - LOGIN (if not already logged in):",
        "  Click 'Sign in', credentials for www.united.com, MileagePlus ka388724.",
        "  If 2FA: read_sms_code (sender 26266). Enter code.",
        "",
        f"STEP 2 - Navigate to: {cash_url}",
        "STEP 3 - wait 15",
        "STEP 4 - Click 'Money + Miles' tab if available.",
        "STEP 5 - wait 10",
        "STEP 6 - screenshot",
        "STEP 7 - done. Report ALL flights with prices (miles or $).",
        f"Focus on fares under {max_miles:,} miles.",
    ])

    agent_run = run_browser_agent_goal(
        goal=goal, url=UNITED_URL, max_steps=60, trace=True, use_vision=True,
    )
    if agent_run["ok"]:
        run_result = agent_run.get("result") or {}
        result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)
        observations.append(f"Agent-only status: {run_result.get('status', 'unknown')}")

        live_matches = _parse_matches(result_text, inputs)
        if not live_matches:
            live_matches = extract_award_matches_from_text(
                result_text, route=f"{origin}-{dest}", cabin=cabin,
                travelers=travelers, max_miles=max_miles,
            )
        for m in live_matches:
            if "booking_url" not in m:
                m["booking_url"] = book_url

        return {
            "mode": "live",
            "real_data": True,
            "matches": live_matches,
            "booking_url": book_url,
            "summary": f"United agent-only: {len(live_matches)} match(es).",
            "raw_observations": observations,
            "errors": [],
        }

    observations.append(f"Agent-only failed: {agent_run['error']}")
    return {
        "mode": "live",
        "real_data": False,
        "matches": [],
        "booking_url": book_url,
        "summary": f"United search failed: {agent_run['error']}",
        "raw_observations": observations,
        "errors": [agent_run["error"]],
    }


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    today = date.today()
    end = today + timedelta(days=int(inputs["days_ahead"]))
    destinations = inputs["to"]
    cabin = str(inputs.get("cabin", "economy"))
    travelers = int(inputs["travelers"])
    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    book_url = _booking_url(inputs["from"], destinations[0], depart_date, cabin, travelers, award=True)

    observations: List[str] = [
        "OpenClaw session expected",
        f"Range: {today.isoformat()}..{end.isoformat()}",
        f"Destinations: {', '.join(destinations)}",
        f"Cabin: {cabin}",
    ]
    if context.get("unresolved_credential_refs"):
        observations.append("Credential refs unresolved.")

    if browser_agent_enabled():
        result = _run_hybrid(inputs, observations)
        if result.get("matches"):
            return result
        observations.append("Hybrid returned no matches, trying agent-only")
        return _run_agent_only(inputs, observations)

    print("WARNING: BrowserAgent not enabled.", file=sys.stderr)
    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": [],
        "booking_url": book_url,
        "summary": "PLACEHOLDER: United search not available",
        "raw_observations": observations,
        "errors": [],
    }
