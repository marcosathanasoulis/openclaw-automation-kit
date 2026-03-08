from __future__ import annotations

import importlib
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import quote

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal
from openclaw_automation.result_extract import extract_award_matches_from_text

UNITED_URL = "https://www.united.com/en/us"
DEFAULT_MILEAGEPLUS_USERNAME = "ka388724"
UNITED_SMS_SENDER = "26266"

_CABIN_MAP = {"economy": "7", "business": "6", "first": "5"}
_FALLBACK_CREDENTIAL_KEYS = {
    "username": (
        "airline_username",
        "username",
        "mileageplus_username",
        "mileageplus_number",
        "united_username",
    ),
    "password": (
        "airline_password",
        "password",
        "united_password",
    ),
}


def _passenger_vector(travelers: int) -> str:
    return ",".join([str(travelers), "0", "0", "0", "0", "0", "0", "0"])


def _booking_url(
    origin: str,
    dest: str,
    depart_date: date,
    cabin: str,
    travelers: int,
    award: bool = False,
) -> str:
    """Build a United search URL.

    `award=True` uses the real `at=1 ... tqp=A` results path instead of the
    older cash / Money+Miles workaround.
    """
    sc = _CABIN_MAP.get(cabin, "7")
    if not award:
        return (
            f"https://www.united.com/en/us/fsr/choose-flights?"
            f"f={origin}&t={dest}&d={depart_date.isoformat()}"
            f"&tt=1&clm=7&taxng=1&newp=1&sc={sc}"
            f"&px={travelers}&idx=1&st=bestmatches"
        )

    px = quote(_passenger_vector(travelers), safe="")
    return (
        f"https://www.united.com/en/us/fsr/choose-flights?"
        f"f={origin}&t={dest}&d={depart_date.isoformat()}"
        f"&tt=1&at=1&sc={sc}&act={travelers}&px={px}"
        f"&taxng=1&newHP=True&clm=7&st=bestmatches&tqp=A"
    )


def _goal(inputs: Dict[str, Any]) -> str:
    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))
    award_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)

    return "\n".join(
        [
            f"Search for United award flights {origin} to {dest}, {travelers} adult(s), {cabin} class.",
            f"Use the real award results path: {award_url}",
            "",
            "If a sign-in modal is visible:",
            "1. If you see a masked MileagePlus number or an invalid-account error, click 'Switch accounts' first.",
            "2. Use credentials for www.united.com.",
            "3. Keep 'Remember me' checked.",
            f"4. If SMS 2FA is requested, use read_sms_code sender={UNITED_SMS_SENDER} keyword=united.",
            "5. After login, wait for the award results to finish loading.",
            "",
            "Then:",
            "- Take a screenshot.",
            "- Done.",
            "- Report whether you see miles prices, a real no-results state, or a blocking error.",
            "- If you see award prices, format them as MATCH|YYYY-MM-DD|MILES|TAXES|STOPS|United|notes",
            "  so the parser can extract them reliably.",
        ]
    )


def _resolved_credential(context: Dict[str, Any], logical_keys: tuple[str, ...]) -> str:
    creds = context.get("credentials") if isinstance(context.get("credentials"), dict) else {}
    for key in logical_keys:
        value = creds.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _load_browser_helpers() -> tuple[Callable[..., Any] | None, Callable[..., Any] | None]:
    module_name = os.getenv("OPENCLAW_BROWSER_AGENT_MODULE", "browser_agent").strip() or "browser_agent"
    module_path = os.getenv("OPENCLAW_BROWSER_AGENT_PATH", "").strip()
    if module_path:
        resolved = str(Path(module_path).expanduser().resolve())
        if resolved in sys.path:
            sys.path.remove(resolved)
        sys.path.insert(0, resolved)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None, None
    return getattr(module, "get_credentials", None), getattr(module, "read_sms_code", None)


def _resolve_united_credentials(context: Dict[str, Any]) -> tuple[str, str]:
    username = _resolved_credential(context, _FALLBACK_CREDENTIAL_KEYS["username"])
    password = _resolved_credential(context, _FALLBACK_CREDENTIAL_KEYS["password"])

    if not username:
        username = (
            os.getenv("OPENCLAW_SECRET_OPENCLAW_UNITED_USERNAME", "").strip()
            or DEFAULT_MILEAGEPLUS_USERNAME
        )
    if not password:
        password = os.getenv("OPENCLAW_SECRET_OPENCLAW_UNITED_PASSWORD", "").strip()

    get_credentials, _ = _load_browser_helpers()
    if get_credentials and (not username or not password):
        try:
            creds = get_credentials("www.united.com")
            if not creds:
                creds = get_credentials("united.com")
            if creds:
                username = username or str(creds[0]).strip()
                password = password or str(creds[1]).strip()
        except Exception:
            pass

    return username, password


def _first_visible(candidates: list[Any]) -> Any | None:
    for candidate in candidates:
        try:
            locator = candidate.first
        except Exception:
            locator = candidate
        try:
            if locator.is_visible():
                return locator
        except Exception:
            continue
    return None


def _click(locator: Any, timeout: int = 5000) -> bool:
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def _fill(locator: Any, value: str) -> bool:
    try:
        locator.click(timeout=3000)
    except Exception:
        pass
    try:
        locator.fill("")
    except Exception:
        pass
    try:
        locator.type(value, delay=80)
        return True
    except Exception:
        try:
            locator.fill(value)
            return True
        except Exception:
            return False


def _try_click_selector(page: Any, selector: str, timeout: int = 3000) -> bool:
    try:
        page.locator(selector).first.click(timeout=timeout)
        return True
    except Exception:
        return False


def _fill_selector(page: Any, selectors: list[str], value: str) -> bool:
    locator = _first_visible([page.locator(selector) for selector in selectors])
    if not locator:
        return False
    return _fill(locator, value)


def _dismiss_united_overlays(page: Any) -> None:
    for locator in (
        page.get_by_role("button", name=re.compile(r"^(?:No thanks|Close)$", re.IGNORECASE)),
        page.locator("button[aria-label='Close']"),
        page.locator("button[aria-label*='Close']"),
    ):
        try:
            if locator.count() > 0:
                _click(locator.first, timeout=1500)
        except Exception:
            continue
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def _is_sign_in_visible(page: Any) -> bool:
    return bool(
        _first_visible(
            [
                page.get_by_role("heading", name=re.compile(r"sign in", re.IGNORECASE)),
                page.get_by_role("button", name=re.compile(r"switch accounts", re.IGNORECASE)),
                page.get_by_label(re.compile(r"password", re.IGNORECASE)),
            ]
        )
    )


def _needs_miles_sign_in(page: Any) -> bool:
    return bool(
        _first_visible(
            [
                page.get_by_text(
                    re.compile(r"must be signed-in to see flight results with miles", re.IGNORECASE)
                ),
                page.get_by_role("button", name=re.compile(r"show flights with money", re.IGNORECASE)),
                page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)),
            ]
        )
    )


def _looks_logged_in(page: Any) -> bool:
    if _needs_miles_sign_in(page):
        return False
    return bool(
        _first_visible(
            [
                page.get_by_text(re.compile(r"\bHi,\s*Marcos\b", re.IGNORECASE)),
                page.get_by_role("link", name=re.compile(r"my trips", re.IGNORECASE)),
                page.get_by_role("button", name=re.compile(r"sign out", re.IGNORECASE)),
            ]
        )
    )


def _wait_for_award_results(page: Any, timeout_s: int = 25) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass
        _dismiss_united_overlays(page)
        state = _page_state(page)
        if state["flight_cards"] or state["miles_mentions"] or state["no_results"]:
            return
        time.sleep(1)


def _set_united_depart_date(page: Any, depart_date: date) -> bool:
    date_str = depart_date.strftime("%m/%d/%Y")
    if _fill_selector(
        page,
        [
            "input#DepartDate",
            "#DepartDate input",
            "input[aria-label*='Depart']",
            "input[placeholder*='Depart']",
        ],
        date_str,
    ):
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
        time.sleep(1)
        return True
    return False


def _set_united_travelers_and_cabin(page: Any, travelers: int, cabin: str) -> list[str]:
    notes: list[str] = []
    if not _try_click_selector(page, "[aria-describedby=uaPaxSelectorMainButtonAriaDescription]"):
        _try_click_selector(page, "text=/travelers|passengers/i")

    time.sleep(1)

    current_adults = 1
    try:
        traveler_text = page.locator("body").inner_text(timeout=2000)
        match = re.search(r"Number of travelers:\s*(\d+)\s+Adults?", traveler_text, re.IGNORECASE)
        if match:
            current_adults = int(match.group(1))
    except Exception:
        pass

    for _ in range(max(0, travelers - current_adults)):
        clicked = False
        for selector in [
            "button:has(span:has-text('Increase number of Adults'))",
            "button[aria-label*='Increase number of Adults']",
            "button[aria-label*='Increase'][aria-label*='Adult']",
            "button[data-testid*='adult'][data-testid*='increase']",
        ]:
            if _try_click_selector(page, selector, timeout=1500):
                clicked = True
                time.sleep(0.4)
                break
        if not clicked:
            notes.append("Unable to increase United adult count deterministically")
            break

    if cabin in {"business", "first"}:
        label = "Business" if cabin == "business" else "First"
        if not _try_click_selector(page, f"text=/{label}(?:\\s+class)?/i", timeout=1500):
            notes.append(f"Unable to select United cabin '{label}' deterministically")

    _try_click_selector(page, "text=/done|close/i", timeout=1500)
    _try_click_selector(page, "button[aria-label='Close']", timeout=1500)
    return notes


def _submit_homepage_award_search(
    page: Any,
    origin: str,
    dest: str,
    depart_date: date,
    cabin: str,
    travelers: int,
    observations: List[str],
) -> bool:
    page.goto(UNITED_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    _dismiss_united_overlays(page)

    _try_click_selector(page, "#radiofield-item-id-flightType-1")
    _try_click_selector(page, "label:has-text('One-way')")

    try:
        award_checkbox = page.locator("#award").first
        if not award_checkbox.is_checked():
            _click(award_checkbox, timeout=1500)
    except Exception:
        _try_click_selector(page, "label:has-text('Book with miles')")
        _try_click_selector(page, "text=/book with miles/i")

    if not _fill_selector(
        page,
        ["#bookFlightOriginInput", "input[id='bookFlightOriginInput']"],
        origin,
    ):
        observations.append("United homepage search: origin field not found")
        return False
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
    time.sleep(1)

    if not _fill_selector(
        page,
        ["#bookFlightDestinationInput", "input[id='bookFlightDestinationInput']"],
        dest,
    ):
        observations.append("United homepage search: destination field not found")
        return False
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
    time.sleep(1)

    if not _set_united_depart_date(page, depart_date):
        observations.append("United homepage search: depart date field not found")
        return False

    observations.extend(_set_united_travelers_and_cabin(page, travelers, cabin))

    if not (
        _try_click_selector(page, "button:has-text('Find flights')", timeout=5000)
        or _try_click_selector(page, "button:has-text('Search')", timeout=5000)
    ):
        observations.append("United homepage search: search button not found")
        return False

    _wait_for_award_results(page, timeout_s=25)
    return True


def _page_state(page: Any) -> Dict[str, Any]:
    try:
        return page.evaluate(
            """() => {
                const body = document.body ? document.body.innerText : "";
                const text = body || "";
                return {
                    body_len: text.length,
                    miles_mentions: (text.match(/miles/gi) || []).length,
                    flight_cards: document.querySelectorAll(
                        '[data-testid*="flight-card"], .flight-card, [class*="FlightCard"]'
                    ).length,
                    skeletons: document.querySelectorAll(
                        '[class*="skeleton"], [data-testid*="skeleton"]'
                    ).length,
                    no_results: /no flights|no results|no award/i.test(text),
                    invalid_credentials: /account information entered is invalid/i.test(text),
                };
            }"""
        )
    except Exception:
        return {
            "body_len": 0,
            "miles_mentions": 0,
            "flight_cards": 0,
            "skeletons": 0,
            "no_results": False,
            "invalid_credentials": False,
        }


def _collect_result_text(page: Any) -> str:
    chunks: list[str] = []
    try:
        body_text = page.locator("body").inner_text(timeout=5000)
        if body_text:
            chunks.append(body_text)
    except Exception:
        pass

    card_locators = [
        page.locator('[data-testid*="flight-card"]'),
        page.locator(".flight-card"),
        page.locator('[class*="FlightCard"]'),
    ]
    for locator in card_locators:
        try:
            count = min(locator.count(), 8)
        except Exception:
            count = 0
        for idx in range(count):
            try:
                text = locator.nth(idx).inner_text(timeout=2000)
            except Exception:
                text = ""
            if text:
                chunks.append(text)

    return "\n".join(part.strip() for part in chunks if part.strip())


def _capture_debug_artifacts(page: Any, label: str) -> list[str]:
    notes: list[str] = []
    stamp = int(time.time())
    shot_path = Path("/tmp") / f"{label}_{stamp}.png"
    text_path = Path("/tmp") / f"{label}_{stamp}.txt"

    try:
        page.screenshot(path=str(shot_path), full_page=False)
        notes.append(f"Debug screenshot: {shot_path}")
    except Exception as exc:
        notes.append(f"Debug screenshot failed: {exc}")

    try:
        body_text = page.locator("body").inner_text(timeout=5000)
        text_path.write_text(body_text[:20000], encoding="utf-8")
        notes.append(f"Debug text: {text_path}")
    except Exception as exc:
        notes.append(f"Debug text failed: {exc}")

    return notes


def _submit_united_otp(page: Any, observations: List[str]) -> tuple[bool, str]:
    _, read_sms_code = _load_browser_helpers()
    if not read_sms_code:
        return False, "United 2FA requested but SMS reader is unavailable"

    code_input = _first_visible(
        [
            page.get_by_label(re.compile(r"(verification|security|one-time).*(code|passcode)", re.IGNORECASE)),
            page.locator("input[autocomplete='one-time-code']"),
            page.locator("input[name*='code']"),
            page.locator("input[id*='code']"),
        ]
    )
    if not code_input:
        return True, ""

    observations.append("United requested SMS 2FA")
    since_ts = time.time() - 60
    code = read_sms_code(
        sender=UNITED_SMS_SENDER,
        keyword="united",
        since_timestamp=since_ts,
        timeout=60,
    )
    if not code:
        return False, "United 2FA requested but no code was received"
    if not _fill(code_input, str(code)):
        return False, "Failed to enter United 2FA code"

    verify_btn = _first_visible(
        [
            page.get_by_role("button", name=re.compile(r"(submit|verify|continue)", re.IGNORECASE)),
            page.locator("button:has-text('Verify')"),
        ]
    )
    if verify_btn:
        _click(verify_btn)
    time.sleep(3)
    return True, ""


def _ensure_united_login(page: Any, context: Dict[str, Any], observations: List[str]) -> tuple[bool, str]:
    username, password = _resolve_united_credentials(context)
    if not username or not password:
        return False, "United credentials are unavailable"

    _dismiss_united_overlays(page)
    if _needs_miles_sign_in(page):
        sign_in_for_miles = _first_visible(
            [
                page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)),
                page.locator("button:has-text('Sign In')"),
            ]
        )
        if sign_in_for_miles:
            _click(sign_in_for_miles)
            time.sleep(2)
            observations.append("United required an extra sign-in for miles pricing")

    if _needs_miles_sign_in(page) and not _is_sign_in_visible(page):
        return False, "United still requires sign-in to view miles results"

    if _looks_logged_in(page) and not _is_sign_in_visible(page):
        observations.append("United already logged in")
        return True, ""

    if not _is_sign_in_visible(page):
        sign_in_cta = _first_visible(
            [
                page.get_by_role("link", name=re.compile(r"^sign in$", re.IGNORECASE)),
                page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)),
            ]
        )
        if sign_in_cta:
            _click(sign_in_cta)
            time.sleep(2)

    if not _is_sign_in_visible(page):
        return True, ""

    switch_accounts = _first_visible(
        [
            page.get_by_role("button", name=re.compile(r"switch accounts", re.IGNORECASE)),
            page.locator("button:has-text('Switch accounts')"),
        ]
    )
    if switch_accounts:
        _click(switch_accounts)
        time.sleep(2)
        observations.append("United login required 'Switch accounts'")

    username_input = _first_visible(
        [
            page.get_by_label(re.compile(r"mileageplus.*number", re.IGNORECASE)),
            page.locator("input[autocomplete='username']"),
            page.locator("input[name*='user']"),
            page.locator("input[id*='user']"),
        ]
    )
    if username_input:
        if not _fill(username_input, username):
            return False, "Failed to enter United username"

    password_input = _first_visible(
        [
            page.get_by_label(re.compile(r"password", re.IGNORECASE)),
            page.locator("input[type='password']"),
            page.locator("input[autocomplete='current-password']"),
        ]
    )
    continue_btn = _first_visible(
        [
            page.get_by_role("button", name=re.compile(r"^continue$", re.IGNORECASE)),
            page.locator("button:has-text('Continue')"),
        ]
    )
    if continue_btn and not password_input:
        _click(continue_btn)
        time.sleep(2)
        password_input = _first_visible(
            [
                page.get_by_label(re.compile(r"password", re.IGNORECASE)),
                page.locator("input[type='password']"),
                page.locator("input[autocomplete='current-password']"),
            ]
        )

    if not password_input:
        return False, "United password field was not visible"
    if not _fill(password_input, password):
        return False, "Failed to enter United password"

    remember_me = _first_visible(
        [
            page.get_by_role("checkbox", name=re.compile(r"remember", re.IGNORECASE)),
            page.get_by_label(re.compile(r"remember", re.IGNORECASE)),
        ]
    )
    if remember_me:
        try:
            if not remember_me.is_checked():
                remember_me.check(timeout=3000)
        except Exception:
            _click(remember_me, timeout=1500)

    sign_in_btn = _first_visible(
        [
            page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)),
            page.locator("button:has-text('Sign in')"),
        ]
    )
    if not sign_in_btn:
        return False, "United sign-in button was not visible"

    _click(sign_in_btn)
    time.sleep(4)

    otp_ok, otp_error = _submit_united_otp(page, observations)
    if not otp_ok:
        return False, otp_error

    if _page_state(page)["invalid_credentials"]:
        return False, "United rejected the provided credentials"

    for _ in range(20):
        if _looks_logged_in(page) and not _is_sign_in_visible(page):
            return True, ""
        if _needs_miles_sign_in(page) and not _is_sign_in_visible(page):
            return False, "United still requires sign-in to view miles results"
        if not _is_sign_in_visible(page):
            return True, ""
        time.sleep(1)

    return False, "United sign-in modal remained visible"


def _run_direct_award_search(
    context: Dict[str, Any],
    inputs: Dict[str, Any],
    observations: List[str],
) -> Dict[str, Any] | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        observations.append("Playwright not available for direct United path")
        return None

    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))
    award_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222").strip()
                or "http://127.0.0.1:9222"
            )
            if not browser.contexts:
                observations.append("Direct United path found no CDP browser contexts")
                return None

            context_pw = browser.contexts[0]
            page = None
            try:
                page = context_pw.new_page()
                observations.append("Direct United path opened a fresh page in the persistent CDP context")
            except Exception as exc:
                observations.append(f"Fresh CDP page unavailable, reusing an existing tab: {exc}")

            if page is None:
                page = next(
                    (
                        candidate
                        for candidate in context_pw.pages
                        if not candidate.is_closed() and "united.com" in candidate.url
                    ),
                    None,
                )
            if page is None:
                page = next(
                    (candidate for candidate in context_pw.pages if not candidate.is_closed()),
                    None,
                )
            if page is None:
                observations.append("Direct United path found no reusable page in the attached CDP context")
                return None

            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(30000)
            page.goto(award_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            observations.append(f"Direct United award URL: {award_url}")

            logged_in, login_error = _ensure_united_login(page, context, observations)
            if not logged_in:
                state = _page_state(page)
                observations.append(f"United direct login failure state: {state}")
                return {
                    "mode": "live",
                    "real_data": False,
                    "matches": [],
                    "booking_url": award_url,
                    "summary": f"United login failed on award page: {login_error}",
                    "raw_observations": observations,
                    "errors": [login_error],
                }

            page.goto(award_url, wait_until="domcontentloaded", timeout=30000)
            _wait_for_award_results(page, timeout_s=25)
            state = _page_state(page)
            if state["flight_cards"] == 0 and state["skeletons"] > 50:
                observations.append(
                    "United direct award URL stalled on skeleton loaders; retrying via homepage submit"
                )
                if _submit_homepage_award_search(
                    page,
                    origin,
                    dest,
                    depart_date,
                    cabin,
                    travelers,
                    observations,
                ):
                    state = _page_state(page)
            observations.append(
                "United direct award page state: "
                f"flight_cards={state['flight_cards']} "
                f"miles_mentions={state['miles_mentions']} "
                f"skeletons={state['skeletons']} "
                f"no_results={state['no_results']}"
            )
            observations.append(f"United current URL: {page.url}")

            result_text = _collect_result_text(page)
            matches = extract_award_matches_from_text(
                result_text,
                route=f"{origin}-{dest}",
                cabin=cabin,
                travelers=travelers,
                max_miles=max_miles,
            )

            if matches:
                best = min(match["miles"] for match in matches)
                return {
                    "mode": "live",
                    "real_data": True,
                    "matches": matches,
                    "booking_url": award_url,
                    "summary": (
                        f"United direct award search: {len(matches)} flight(s) found. "
                        f"Best: {best:,} miles."
                    ),
                    "raw_observations": observations,
                    "errors": [],
                }

            if state["no_results"]:
                return {
                    "mode": "live",
                    "real_data": True,
                    "matches": [],
                    "booking_url": award_url,
                    "summary": "United direct award search completed: no flights found.",
                    "raw_observations": observations,
                    "errors": [],
                }

            if state["invalid_credentials"]:
                return {
                    "mode": "live",
                    "real_data": False,
                    "matches": [],
                    "booking_url": award_url,
                    "summary": "United rejected the provided credentials on the award page.",
                    "raw_observations": observations,
                    "errors": ["United rejected credentials"],
                }

            observations.append("Direct United path loaded a page but did not yield parseable award data")
            observations.extend(_capture_debug_artifacts(page, "united_direct_debug"))
            return {
                "mode": "live",
                "real_data": False,
                "matches": [],
                "booking_url": award_url,
                "summary": "United award page loaded, but the parser could not extract reliable award results.",
                "raw_observations": observations,
                "errors": [],
            }
    except Exception as exc:
        observations.append(f"Direct United path failed before a reliable result: {exc}")
        return None


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

    depart_date = today + timedelta(days=int(inputs["days_ahead"]))
    award_url = _booking_url(
        inputs["from"], destinations[0], depart_date, cabin, travelers, award=True,
    )

    direct_result = _run_direct_award_search(context, inputs, observations)
    if direct_result is not None:
        return direct_result

    if browser_agent_enabled():
        agent_run = run_browser_agent_goal(
            goal=_goal(inputs),
            url=award_url,
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
                    "BrowserAgent fallback executed.",
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
                best = min(match["miles"] for match in extracted_matches)
                summary_parts.append(f"Best: {best:,} miles")
            return {
                "mode": "live",
                "real_data": True,
                "matches": extracted_matches,
                "booking_url": award_url,
                "summary": ". ".join(summary_parts) + ".",
                "raw_observations": observations,
                "errors": [],
            }
        observations.append(f"BrowserAgent fallback error: {agent_run['error']}")

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
            "booking_url": award_url,
            "notes": "placeholder result",
        }
    ]

    return {
        "mode": "placeholder",
        "real_data": False,
        "matches": matches,
        "booking_url": award_url,
        "summary": f"PLACEHOLDER: Found {len(matches)} synthetic match(es) <= {max_miles} miles",
        "raw_observations": observations,
        "errors": [],
    }
