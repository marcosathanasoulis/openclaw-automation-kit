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
            if 1000 <= miles <= max_miles:
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
    """Hybrid: BrowserAgent login + Playwright form fill + scrape."""
    from playwright.sync_api import sync_playwright

    origin = inputs["from"]
    dest = inputs["to"][0]
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    cdp_url = os.environ.get("BROWSER_CDP_URL", "http://127.0.0.1:9222")

    # Phase 1: BrowserAgent login
    observations.append("Phase 1: BrowserAgent login to ANA award system")
    login_run = adaptive_run(
        goal=_login_goal(),
        url=ANA_AWARD_URL,
        max_steps=20,
        airline="ana_login",
        inputs=inputs,
        max_attempts=2,
        trace=True,
        use_vision=True,
    )

    login_result = login_run.get("result") or {}
    login_text = login_result.get("result", "") if isinstance(login_result, dict) else str(login_result)
    login_ok = login_run.get("ok", False)
    observations.append(f"Login {'succeeded' if login_ok else 'failed'}: {login_run.get('diag', 'unknown')}")

    # Check for server maintenance
    if "maintenance" in login_text.lower() or "heavy traffic" in login_text.lower():
        observations.append("ANA server maintenance detected - cannot proceed")
        return [], observations

    if not login_ok:
        observations.append("Login failed, attempting search anyway")

    # Phase 2: Playwright form fill + search
    observations.append("Phase 2: Playwright form fill + search")
    all_matches = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            current_url = page.url
            observations.append(f"Current URL: {current_url}")

            # Check if we're on the search form or need to navigate
            if "award_search" not in current_url and "aswbe-i.ana.co.jp" not in current_url:
                observations.append("Not on award page, navigating...")
                page.goto(ANA_AWARD_URL, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)

            # Try to fill the search form via JS
            observations.append("Attempting to fill search form")

            # Check what's on the page
            page_check = page.evaluate("""
                () => ({
                    url: location.href,
                    title: document.title,
                    hasForm: !!document.querySelector('form'),
                    hasDepField: !!document.querySelector('[id*=dep], [name*=dep], [id*=origin], [name*=origin]'),
                    hasArrField: !!document.querySelector('[id*=arr], [name*=arr], [id*=dest], [name*=dest]'),
                    hasSearchBtn: !!document.querySelector('[type=submit], button[class*=search], input[value*=Search]'),
                    hasError: !!document.querySelector('[class*=error], [class*=maintenance]'),
                    bodySnippet: (document.body?.innerText || '').substring(0, 500),
                    inputCount: document.querySelectorAll('input, select').length,
                })
            """)
            observations.append(f"Form check: inputs={page_check.get('inputCount', 0)}, "
                                f"depField={page_check.get('hasDepField')}, "
                                f"error={page_check.get('hasError')}")

            if page_check.get("hasError"):
                body = page_check.get("bodySnippet", "")
                if "maintenance" in body.lower() or "heavy traffic" in body.lower():
                    observations.append("Server maintenance on search page")
                    return [], observations

            # Fill departure airport
            dep_filled = page.evaluate(f"""
                () => {{
                    const fields = document.querySelectorAll('input[id*=dep], input[name*=dep], input[id*=origin], input[name*=origin]');
                    for (const f of fields) {{
                        f.value = '{origin}';
                        f.dispatchEvent(new Event('input', {{bubbles: true}}));
                        f.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            observations.append(f"Departure filled: {dep_filled}")
            time.sleep(1)

            # Fill arrival airport
            arr_filled = page.evaluate(f"""
                () => {{
                    const fields = document.querySelectorAll('input[id*=arr], input[name*=arr], input[id*=dest], input[name*=dest]');
                    for (const f of fields) {{
                        f.value = '{dest}';
                        f.dispatchEvent(new Event('input', {{bubbles: true}}));
                        f.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            observations.append(f"Arrival filled: {arr_filled}")
            time.sleep(1)

            # Set date
            date_str = depart_date.strftime("%m/%d/%Y")
            date_filled = page.evaluate(f"""
                () => {{
                    const fields = document.querySelectorAll('input[id*=date], input[name*=date], input[type=date]');
                    for (const f of fields) {{
                        f.value = '{date_str}';
                        f.dispatchEvent(new Event('input', {{bubbles: true}}));
                        f.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return true;
                    }}
                    return false;
                }}
            """)
            observations.append(f"Date filled: {date_filled}")

            # Click search
            time.sleep(2)
            search_clicked = page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('[type=submit], button[class*=search], input[value*=Search], a[class*=search]');
                    for (const b of btns) {
                        b.click();
                        return true;
                    }
                    return false;
                }
            """)
            observations.append(f"Search clicked: {search_clicked}")

            # Wait for results
            time.sleep(20)

            # Extract results
            extracted = page.evaluate(_extract_results_js())
            observations.append(f"Results extracted: {extracted.get('resultsCount', 0)} items")
            observations.append(f"Page title: {extracted.get('title', 'unknown')}")

            # Build text from extracted data
            result_lines = extracted.get("results", [])
            body_snippet = extracted.get("bodySnippet", "")
            full_text = "\n".join(result_lines) + "\n" + body_snippet

            all_matches = _parse_matches(full_text, inputs)
            observations.append(f"Parsed {len(all_matches)} matches")

            # If no matches from structured extraction, try the full body
            if not all_matches and body_snippet:
                all_matches = _parse_matches(body_snippet, inputs)
                observations.append(f"Body text matches: {len(all_matches)}")

    except Exception as e:
        observations.append(f"Playwright error: {str(e)[:200]}")

    return all_matches, observations


def _run_agent_only(context: Dict[str, Any], inputs: Dict[str, Any], observations: List[str]):
    """Fallback: pure BrowserAgent approach."""
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    cabin_display = CABIN_DISPLAY.get(cabin, cabin.title())
    days_ahead = int(inputs["days_ahead"])
    depart_date = date.today() + timedelta(days=days_ahead)

    goal = f"""Search for ANA award flights {origin} to {dest} on {depart_date.strftime('%B %-d, %Y')}, {cabin_display}, {travelers} passengers.

1. You are on the ANA award search login page.
2. credentials for www.ana.co.jp
3. Enter AMC Number and password, click Login.
4. wait 10
5. If you see the search form, fill departure ({origin}), arrival ({dest}), date ({depart_date.strftime('%m/%d/%Y')}), cabin ({cabin_display}), {travelers} adults.
6. Click Search. wait 15.
7. screenshot and report all visible flights with miles cost.
8. If server maintenance error, report done with that info.
"""

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
        return {
            "mode": "placeholder",
            "real_data": False,
            "matches": [],
            "summary": "PLACEHOLDER: ANA search not available (no browser agent)",
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
