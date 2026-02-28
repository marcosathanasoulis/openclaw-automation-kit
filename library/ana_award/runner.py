from __future__ import annotations

import os
import re
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from openclaw_automation.browser_agent_adapter import browser_agent_enabled
from openclaw_automation.adaptive import adaptive_run
from openclaw_automation.result_extract import extract_award_matches_from_text

ANA_URL = "https://www.ana.co.jp/en/us/"
ANA_AWARD_URL = "https://aswbe-i.ana.co.jp/international_asw/pages/award/search/roundtrip/award_search_roundtrip_input.xhtml?CONNECTION_KIND=JPN&LANG=en"

CABIN_MAP = {
    "economy": "Y",
    "premium_economy": "PY",
    "business": "C",
    "first": "F",
}

CABIN_DISPLAY = {
    "economy": "Economy Class",
    "premium_economy": "Premium Economy",
    "business": "Business Class",
    "first": "First Class",
}


def _login_goal():
    return """Login to ANA Mileage Club award search.

1. You are on the ANA award search login page (aswbe-i.ana.co.jp).
2. Look for the AMC Number and Password fields.
3. credentials for www.ana.co.jp
4. Enter the AMC Number (10-digit member number) in the member number field.
5. Enter the password in the password field.
6. Click 'Login' or 'Sign In' to submit.
7. wait 10
8. If you see the award search form (departure/arrival fields), login succeeded. Report done.
9. If you see 'heavy traffic' or 'server maintenance', report done with that info.
10. If login fails, try once more, then report done.

CRITICAL: Do NOT navigate away from the award search pages."""


def _extract_results_js():
    """JS to extract award search results from ANA's results page."""
    return """
    (() => {
        const results = [];
        // Look for flight result rows
        const rows = document.querySelectorAll('.award-result, .result-row, tr[class*=flight], .flightRow, .resultRow');
        rows.forEach(row => {
            results.push('ROW: ' + row.textContent.replace(/\\s+/g, ' ').trim().substring(0, 300));
        });
        
        // Look for availability calendar (O/X pattern)
        const cells = document.querySelectorAll('td[class*=avail], .calendar-cell, td.av, td.seat');
        cells.forEach(cell => {
            const text = cell.textContent.trim();
            if (text === 'O' || text === 'X' || text.match(/\\d+/)) {
                const dateEl = cell.closest('tr')?.querySelector('td:first-child');
                results.push('AVAIL: ' + (dateEl?.textContent?.trim() || '') + ' ' + text);
            }
        });
        
        // Look for miles amounts anywhere
        const allText = document.body?.innerText || '';
        const milesLines = allText.split('\\n').filter(l => /\\d[\\d,]*\\s*(?:miles?|mi)/i.test(l));
        milesLines.forEach(l => results.push('MILES_LINE: ' + l.trim().substring(0, 200)));
        
        // Look for any table with flight data
        const tables = document.querySelectorAll('table');
        tables.forEach((t, i) => {
            if (t.textContent.match(/miles|award|economy|business|first/i)) {
                results.push('TABLE_' + i + ': ' + t.textContent.replace(/\\s+/g, ' ').trim().substring(0, 500));
            }
        });
        
        // Get page title/headers for context
        const h1 = document.querySelector('h1, h2, .page-title');
        if (h1) results.push('TITLE: ' + h1.textContent.trim());
        
        // Check for error messages
        const errors = document.querySelectorAll('.error, .alert, .message, [class*=error], [class*=maintenance]');
        errors.forEach(e => results.push('ERROR: ' + e.textContent.trim().substring(0, 200)));
        
        return {
            url: location.href,
            title: document.title,
            resultsCount: results.length,
            results: results.slice(0, 50),
            bodySnippet: (document.body?.innerText || '').substring(0, 2000),
        };
    })()
    """


def _parse_matches(result_text: str, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result_text:
        return []

    origin = inputs["from"]
    dest = inputs["to"][0]
    cabin = inputs.get("cabin", "economy")
    travelers = int(inputs.get("travelers", 1))
    max_miles = int(inputs.get("max_miles", 999999))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))

    matches = []

    # Pattern: miles amounts
    miles_pattern = re.compile(r'([\d,]+)\s*(?:miles|mi)\b', re.IGNORECASE)
    for line in result_text.split("\n"):
        mm = miles_pattern.search(line)
        if mm:
            miles = int(mm.group(1).replace(",", ""))
            if 1000 <= miles <= max_miles * 2:  # soft cap: report slightly over-budget results
                matches.append({
                    "route": f"{origin}-{dest}",
                    "date": depart_date.isoformat(),
                    "miles": miles,
                    "travelers": travelers,
                    "cabin": cabin,
                    "mixed_cabin": False,
                    "notes": line.strip()[:150],
                })

    # Availability calendar pattern: O = available
    avail_pattern = re.compile(r'(?:AVAIL|DATE).*?(\d{1,2}[/-]\d{1,2}).*?(O|available)', re.IGNORECASE)
    for m in avail_pattern.finditer(result_text):
        matches.append({
            "route": f"{origin}-{dest}",
            "date": m.group(1),
            "miles": 0,
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "notes": f"Available: {m.group(0).strip()[:150]}",
        })

    # Also try standard extractor
    if not matches:
        matches = extract_award_matches_from_text(
            result_text,
            route=f"{origin}-{dest}",
            cabin=cabin,
            travelers=travelers,
            max_miles=max_miles,
        )

    return matches


def _run_hybrid(context: Dict[str, Any], inputs: Dict[str, Any], observations: List[str]):
    """Hybrid: BrowserAgent login + Playwright form fill + scrape.
    Runs Playwright in a daemon thread to avoid asyncio event loop contamination
    from the prior adaptive_run() call.
    """
    import threading as _threading
    from playwright.sync_api import sync_playwright

    origin = inputs["from"]
    dest = inputs["to"][0]
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)
    cdp_url = os.environ.get("OPENCLAW_CDP_URL", os.environ.get("BROWSER_CDP_URL", "http://127.0.0.1:9222"))

    # Phase 1: BrowserAgent login
    observations.append("Phase 1: BrowserAgent login to ANA award system")
    login_run = adaptive_run(
        goal=_login_goal(),
        url=ANA_AWARD_URL,
        max_steps=20,
        airline="ana_login",
        inputs=inputs,
        max_attempts=1,
        trace=True,
        use_vision=True,
    )

    login_result = login_run.get("result") or {}
    login_text = login_result.get("result", "") if isinstance(login_result, dict) else str(login_result)
    login_ok = login_run.get("ok", False)
    observations.append(f"Login {'succeeded' if login_ok else 'failed'}")

    if "maintenance" in login_text.lower() or "heavy traffic" in login_text.lower():
        observations.append("ANA server maintenance detected")
        return [], observations

    # Phase 2: Playwright form fill in a separate thread
    observations.append("Phase 2: Playwright form fill + search")
    pw_matches: list = []
    pw_errors: list = []

    def _pw_worker():
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    pw_errors.append("No browser contexts after login")
                    return

                ctx = contexts[0]
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                current_url = page.url
                observations.append(f"Playwright connected, URL: {current_url}")

                # Navigate to ANA award search if not already there
                if "aswbe-i.ana.co.jp" not in current_url:
                    observations.append("Navigating to ANA award search page")
                    page.goto(ANA_AWARD_URL, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(5)

                # Check page state
                page_check = page.evaluate("""
                    () => ({
                        url: location.href,
                        title: document.title,
                        inputCount: document.querySelectorAll('input, select').length,
                        hasError: !!(document.body?.innerText || '').match(/maintenance|heavy traffic/i),
                        bodySnippet: (document.body?.innerText || '').substring(0, 500),
                    })
                """)
                observations.append(f"ANA page: {page_check.get('title', '?')} | inputs={page_check.get('inputCount', 0)}")

                if page_check.get("hasError"):
                    pw_errors.append("ANA server maintenance")
                    return

                date_str = depart_date.strftime("%m/%d/%Y")

                # Fill form fields using JS (ANA uses a server-side form, not Vue.js)
                filled = page.evaluate(f"""
                    () => {{
                        let filled = {{}};
                        // Origin
                        const dep = document.querySelector('select[name*=dep], select[name*=origin], select[id*=dep], select[id*=origin]');
                        if (dep) {{
                            const opt = Array.from(dep.options).find(o => o.value.includes('{origin}') || o.text.includes('{origin}'));
                            if (opt) {{ dep.value = opt.value; dep.dispatchEvent(new Event('change', {{bubbles: true}})); filled.dep = opt.value; }}
                        }}
                        // Destination
                        const arr = document.querySelector('select[name*=arr], select[name*=dest], select[id*=arr], select[id*=dest]');
                        if (arr) {{
                            const opt = Array.from(arr.options).find(o => o.value.includes('{dest}') || o.text.includes('{dest}'));
                            if (opt) {{ arr.value = opt.value; arr.dispatchEvent(new Event('change', {{bubbles: true}})); filled.arr = opt.value; }}
                        }}
                        // Date
                        const dateInputs = document.querySelectorAll('input[name*=date], input[id*=date]');
                        for (const di of dateInputs) {{
                            di.value = '{date_str}';
                            di.dispatchEvent(new Event('input', {{bubbles: true}}));
                            di.dispatchEvent(new Event('change', {{bubbles: true}}));
                            filled.date = '{date_str}';
                        }}
                        return filled;
                    }}
                """)
                observations.append(f"Form fill result: {filled}")
                time.sleep(2)

                # Submit search
                search_clicked = page.evaluate("""
                    () => {
                        const btn = document.querySelector('input[type=submit], button[type=submit], input[value*=Search], button.search-button');
                        if (btn) { btn.click(); return btn.value || btn.textContent.trim(); }
                        return null;
                    }
                """)
                observations.append(f"Search submitted: {search_clicked}")

                # Wait for results
                observations.append("Waiting 25s for ANA results...")
                time.sleep(25)

                # Extract results
                extracted = page.evaluate(_extract_results_js())
                observations.append(f"Extracted {extracted.get('resultsCount', 0)} items from ANA results")

                result_lines = extracted.get("results", [])
                body_snippet = extracted.get("bodySnippet", "")
                full_text = "\n".join(result_lines) + "\n" + body_snippet

                parsed = _parse_matches(full_text, inputs)
                if parsed:
                    pw_matches.extend(parsed)
                elif body_snippet:
                    parsed2 = _parse_matches(body_snippet, inputs)
                    pw_matches.extend(parsed2)
                observations.append(f"Parsed {len(pw_matches)} matches from Playwright phase")

        except Exception as exc:
            pw_errors.append(str(exc))
            observations.append(f"Playwright hybrid error: {str(exc)[:200]}")

    _t = _threading.Thread(target=_pw_worker, daemon=True)
    _t.start()
    _t.join(timeout=300)
    if _t.is_alive():
        pw_errors.append("Playwright phase timed out after 300s")
        observations.append("Playwright phase timed out")

    return pw_matches, observations


def _run_agent_only(context: Dict[str, Any], inputs: Dict[str, Any], observations: List[str]):
    """Fallback: pure BrowserAgent approach."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_DISPLAY.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    end_date = date.today() + timedelta(days=days_ahead)
    goal = "\n".join([
        f"Search for ANA Mileage Club award flights {origin} to {dest}.",
        f"Find ALL dates with award availability from today through {end_date.strftime('%b %-d, %Y')}.",
        f"Cabin: {cabin_display} | Passengers: {travelers}",
        "",
        "=== STEP 1 — LOGIN ===",
        "You are on the ANA international award search page (aswbe-i.ana.co.jp).",
        "Look for 'AMC No.' and 'Password' fields.",
        "credentials for www.ana.co.jp",
        "Enter the 10-digit AMC number in the AMC No. field.",
        "Enter the password in the Password field.",
        "Click the 'Log in' button. wait 10.",
        "If you see 'heavy traffic' or 'maintenance', report done with that message.",
        "",
        "=== STEP 2 — FILL SEARCH FORM ===",
        "After login, look for the search form with departure/arrival fields.",
        f"Set Departure City to: {origin} (San Francisco)",
        f"Set Arrival City to: {dest}",
        f"Set Date to: {depart_date.strftime('%m/%d/%Y')}",
        f"Set Cabin to: {cabin_display}",
        f"Set Adults to: {travelers}",
        "Click the 'Search' or 'Find' button.",
        "wait 15",
        "",
        "=== STEP 3 — READ AVAILABILITY CALENDAR ===",
        "ANA shows an availability calendar with O (available) and X (not available) for each date.",
        "3a. Read ALL dates visible in the calendar and note which are O (available).",
        "3b. If there are 'next week' or forward navigation buttons, click them to see more dates.",
        "3c. Continue for up to 4 weeks.",
        "",
        "=== STEP 4 — VIEW FLIGHT DETAILS ===",
        "For the FIRST available date (O), click to see flight details and miles cost.",
        "Note the flight number, departure/arrival times, and miles required.",
        "",
        "=== STEP 5 — SCREENSHOT AND REPORT ===",
        "screenshot",
        "done",
        "Report in this format:",
        "DATE_CALENDAR: [date] O | [date] X | [date] O | ...",
        "FLIGHT: NH[number] | [dep_time]-[arr_time] | [miles] miles | [cabin]",
        "CHEAPEST: [date] — [miles] miles",
        "",
        "CRITICAL: Report ALL available dates (O) and their miles prices.",
        "Include flights even if over 200,000 miles.",
    ])

    observations.append("Fallback: BrowserAgent-only approach")
    agent_run = adaptive_run(
        goal=goal,
        url=ANA_AWARD_URL,
        max_steps=35,
        airline="ana",
        inputs=inputs,
        max_attempts=1,
        trace=True,
        use_vision=True,
    )

    if agent_run["ok"]:
        run_result = agent_run.get("result") or {}
        result_text = run_result.get("result", "") if isinstance(run_result, dict) else str(run_result)
        live_matches = _parse_matches(result_text, inputs)
        observations.append(f"Agent matches: {len(live_matches)}")
        return live_matches, observations

    observations.append(f"Agent error: {agent_run.get('error', 'unknown')}")
    return [], observations


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

    if not browser_agent_enabled():
        travelers = int(inputs.get("travelers", 1))
        max_miles = int(inputs.get("max_miles", 999999))
        depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))
        placeholder_matches = [{
            "route": f"{inputs['from']}-{destinations[0]}",
            "date": depart_date.isoformat(),
            "miles": min(75000, max_miles),
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "booking_url": ANA_AWARD_URL,
            "notes": "placeholder result",
        }]
        return {
            "mode": "placeholder",
            "real_data": False,
            "matches": placeholder_matches,
            "summary": f"PLACEHOLDER: Found {len(placeholder_matches)} synthetic ANA match(es)",
            "raw_observations": observations,
            "errors": [],
        }

    # Try hybrid approach first
    all_matches, observations = _run_hybrid(context, inputs, observations)

    # If hybrid fails, try agent-only as fallback
    if not all_matches:
        observations.append("Hybrid approach returned no matches, trying agent-only fallback")
        all_matches, observations = _run_agent_only(context, inputs, observations)

    return {
        "mode": "live",
        "real_data": bool(all_matches),
        "matches": all_matches,
        "booking_url": ANA_AWARD_URL,
        "summary": (
            f"ANA award search: {len(all_matches)} flight(s) found for {inputs['from']}-{destinations[0]}. "
            + (f"Best: {min(m['miles'] for m in all_matches if m['miles'] > 0):,} miles. "
               if any(m['miles'] > 0 for m in all_matches) else "")
        ) if all_matches else "ANA award search: no results found.",
        "raw_observations": observations,
        "errors": [],
    }
