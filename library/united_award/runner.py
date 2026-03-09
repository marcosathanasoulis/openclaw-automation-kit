from __future__ import annotations

import importlib
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List
from urllib.parse import quote

from openclaw_automation.browser_agent_adapter import browser_agent_enabled, run_browser_agent_goal
from openclaw_automation.result_extract import extract_award_matches_from_text

UNITED_URL = "https://www.united.com/en/us"
DEFAULT_MILEAGEPLUS_USERNAME = "ka388724"
UNITED_SMS_SENDER = ("26266", "united_airlines")

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
            f"4. If SMS 2FA is requested, use read_sms_code sender={UNITED_SMS_SENDER} and do not require a keyword match.",
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
        resolved = Path(module_path).expanduser().resolve()
        if resolved.is_file():
            module_name = os.getenv("OPENCLAW_BROWSER_AGENT_MODULE", "").strip() or resolved.stem
            search_path = str(resolved.parent)
        else:
            search_path = str(resolved)
        if search_path in sys.path:
            sys.path.remove(search_path)
        sys.path.insert(0, search_path)
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
            creds = None
            if username:
                creds = get_credentials("www.united.com", username)
                if not creds:
                    creds = get_credentials("united.com", username)
            if not creds:
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
        locator.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        pass
    try:
        locator.click(timeout=timeout, force=True)
        return True
    except Exception:
        pass
    try:
        locator.evaluate("(el) => el.click()")
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
        locator = page.locator(selector)
        count = locator.count()
    except Exception:
        return False

    for idx in range(min(count, 12)):
        try:
            candidate = locator.nth(idx)
            if candidate.is_visible() and _click(candidate, timeout=timeout):
                return True
        except Exception:
            continue
    if count:
        try:
            return _click(locator.first, timeout=timeout)
        except Exception:
            return False
    return False


def _try_click_any(page: Any, selectors: list[str], timeout: int = 3000) -> bool:
    for selector in selectors:
        if _try_click_selector(page, selector, timeout=timeout):
            return True
    return False


def _fill_selector(page: Any, selectors: list[str], value: str) -> bool:
    locator = _first_visible([page.locator(selector) for selector in selectors])
    if not locator:
        return False
    return _fill(locator, value)


def _goto_with_retry(page: Any, url: str, observations: List[str], attempts: int = 3) -> bool:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as exc:
            last_error = str(exc)
            observations.append(f"United goto retry {attempt}/{attempts} failed: {exc}")
            time.sleep(min(3 * attempt, 8))
    observations.append(f"United navigation failed after {attempts} attempts: {last_error}")
    return False


def _page_is_live(page: Any | None) -> bool:
    if page is None:
        return False
    try:
        return not page.is_closed()
    except Exception:
        return False


def _active_united_page(context_pw: Any, current_page: Any | None = None) -> Any | None:
    try:
        pages = list(context_pw.pages)
    except Exception:
        return current_page if _page_is_live(current_page) else None

    united_pages = [
        page for page in pages
        if _page_is_live(page) and "united.com" in (page.url or "")
    ]
    if united_pages:
        return united_pages[-1]

    live_pages = [page for page in pages if _page_is_live(page)]
    if live_pages:
        return live_pages[-1]

    return current_page if _page_is_live(current_page) else None


def _wait_for_active_united_page(
    context_pw: Any,
    current_page: Any | None = None,
    timeout_s: float = 8.0,
) -> Any | None:
    deadline = time.time() + max(timeout_s, 0.0)
    candidate = _active_united_page(context_pw, current_page)
    while candidate is None and time.time() < deadline:
        time.sleep(0.5)
        candidate = _active_united_page(context_pw, current_page)
    return candidate


def _page_inventory(context_pw: Any) -> List[str]:
    inventory: List[str] = []
    try:
        pages = list(context_pw.pages)
    except Exception as exc:
        return [f"<context pages unavailable: {exc}>"]

    for page in pages:
        try:
            url = page.url or "<blank>"
        except Exception:
            url = "<url unavailable>"
        inventory.append(f"{'closed' if not _page_is_live(page) else 'live'}:{url}")
    return inventory or ["<no pages>"]


def _select_cdp_context(browser: Any, preferred_host: str = "united.com") -> tuple[Any | None, Any | None]:
    try:
        contexts = list(browser.contexts)
    except Exception:
        return None, None

    fallback_context = None
    fallback_page = None
    for context in contexts:
        candidate = _active_united_page(context)
        if _page_is_live(candidate) and preferred_host in ((candidate.url or "").lower()):
            return context, candidate
        if fallback_context is None:
            fallback_context = context
            fallback_page = candidate if _page_is_live(candidate) else None

    return fallback_context, fallback_page


def _wait_for_active_united_page_in_browser(
    browser: Any,
    current_context: Any | None = None,
    current_page: Any | None = None,
    timeout_s: float = 8.0,
    preferred_host: str = "united.com",
) -> tuple[Any | None, Any | None]:
    deadline = time.time() + max(timeout_s, 0.0)
    context = current_context
    page = current_page if _page_is_live(current_page) else None
    while time.time() <= deadline:
        found_context, found_page = _select_cdp_context(browser, preferred_host=preferred_host)
        if found_context is not None:
            context = found_context
        if _page_is_live(found_page):
            return context, found_page
        time.sleep(0.5)
    return context, page


def _browser_page_inventory(browser: Any) -> List[str]:
    inventory: List[str] = []
    try:
        contexts = list(browser.contexts)
    except Exception as exc:
        return [f"<browser contexts unavailable: {exc}>"]

    for index, context in enumerate(contexts):
        for entry in _page_inventory(context):
            inventory.append(f"context[{index}] {entry}")
    return inventory or ["<no contexts>"]


def _dismiss_united_overlays(page: Any) -> None:
    for locator in (
        page.get_by_role("button", name=re.compile(r"accept cookies", re.IGNORECASE)),
        page.locator("a:has-text('Accept cookies')"),
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


def _collapse_united_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()) if text else ""


def _parse_united_calendar_date(month_name: str, day: str, year: str) -> date | None:
    try:
        return datetime.strptime(f"{month_name} {int(day)} {int(year)}", "%B %d %Y").date()
    except ValueError:
        return None


def _count_united_calendar_days(text: str) -> int:
    normalized = _collapse_united_text(text)
    if not normalized:
        return 0
    return len(
        re.findall(
            r"(?:Choose|Now Showing)\s+[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+with fares starting (?:at|from)",
            normalized,
            re.IGNORECASE,
        )
    )


def _wait_for_award_results(page: Any, timeout_s: int = 25) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not _page_is_live(page):
            return
        try:
            page.wait_for_load_state("networkidle", timeout=2000)
        except Exception:
            pass
        _dismiss_united_overlays(page)
        state = _page_state(page)
        if state["flight_cards"] or state["no_results"]:
            return
        if state["skeletons"] < 40 and state["miles_mentions"] >= 20:
            return
        try:
            body_text = page.locator("body").inner_text(timeout=2000)
        except Exception:
            body_text = ""
        if _count_united_calendar_days(body_text) >= 5:
            return
        if state["skeletons"] < 120 and re.search(r"Select fare for", body_text, re.IGNORECASE):
            return
        time.sleep(1)


def _set_united_depart_date(page: Any, depart_date: date) -> bool:
    date_str = depart_date.strftime("%m/%d/%Y")
    if _fill_selector(
        page,
        [
            "input#DepartDate_start",
            "#DepartDate_start",
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
    if not _try_click_any(
        page,
        [
            "input[type='button'][value*='Adult']",
            "[aria-describedby=uaPaxSelectorMainButtonAriaDescription]",
            "text=/Number of travelers:/i",
            "button:has-text('Travelers')",
        ],
    ):
        _try_click_selector(page, "text=/travelers|passengers/i")

    time.sleep(1)

    current_adults = 1
    try:
        traveler_text = page.locator("body").inner_text(timeout=2000)
        match = re.search(r"Number of travelers:\s*(\d+)\s+Adults?", traveler_text, re.IGNORECASE)
        if not match:
            match = re.search(r"Total:\s*(\d+)\s+Adults?", traveler_text, re.IGNORECASE)
        if match:
            current_adults = int(match.group(1))
    except Exception:
        pass

    for _ in range(max(0, travelers - current_adults)):
        clicked = False
        for selector in [
            "button:has-text('Increase number of Adults')",
            "text=/Increase number of Adults/i",
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
        if not _try_click_any(
            page,
            [
                f"button:has-text('{label}')",
                f"[role='button']:has-text('{label}')",
                f"[role='tab']:has-text('{label}')",
                f"label:has-text('{label}')",
                f"text=/{label}(?:\\s+class)?/i",
            ],
            timeout=1500,
        ):
            notes.append(f"Unable to select United cabin '{label}' deterministically")

    _try_click_any(
        page,
        [
            "button:has-text('Apply')",
            "button:has-text('Close dialog')",
            "text=/done|close/i",
            "button[aria-label='Close']",
        ],
        timeout=1500,
    )
    return notes


def _set_united_travelers_only(page: Any, travelers: int) -> list[str]:
    return _set_united_travelers_and_cabin(page, travelers, cabin="")


def _submit_homepage_award_search(
    page: Any,
    origin: str,
    dest: str,
    depart_date: date,
    cabin: str,
    travelers: int,
    observations: List[str],
) -> bool:
    if not _goto_with_retry(page, UNITED_URL, observations, attempts=2):
        return False
    time.sleep(3)
    _dismiss_united_overlays(page)
    _try_click_any(page, ["a:has-text('Accept cookies')", "text=/Accept cookies/i"], timeout=1500)

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

    observations.extend(_set_united_travelers_only(page, travelers))

    if not (
        _try_click_any(
            page,
            [
                "button[aria-label='Find flights']",
                "button:has-text('Find flights')",
            ],
            timeout=5000,
        )
    ):
        observations.append("United homepage search: search button not found")
        return False

    _wait_for_award_results(page, timeout_s=25)
    state = _page_state(page)
    try:
        body_text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        body_text = ""
    if _looks_like_united_results_page(page, state, body_text):
        return True
    observations.append("United homepage search did not reach a reliable results page")
    return False


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


def _looks_like_united_results_page(page: Any, state: Dict[str, Any], body_text: str) -> bool:
    if not _page_is_live(page):
        return False
    try:
        page_url = page.url or ""
    except Exception:
        page_url = ""
    normalized = body_text or ""
    has_result_rows = bool(re.search(r"Select fare for", normalized, re.IGNORECASE))
    has_results_shell = "Flight Search Results" in normalized
    if state["no_results"]:
        return "choose-flights" in page_url
    if state["flight_cards"]:
        return True
    if _count_united_calendar_days(normalized) >= 5:
        return True
    if has_result_rows and state["miles_mentions"] >= 20:
        return True
    if "choose-flights" in page_url and has_results_shell and state["miles_mentions"] >= 20:
        return True
    return False


def _normalize_united_miles(raw: str) -> int:
    value = raw.strip().lower().replace(",", "")
    if value.endswith("k"):
        return int(float(value[:-1]) * 1000)
    return int(float(value))


def _extract_united_calendar_matches_from_text(
    text: str,
    *,
    route: str,
    travelers: int,
    cabin: str,
    max_miles: int,
) -> List[Dict[str, Any]]:
    normalized = _collapse_united_text(text)
    if not normalized:
        return []

    calendar_pattern = re.compile(
        r"(?:(?:Choose)|(?:Now Showing))\s+[A-Za-z]+,\s+"
        r"(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})\s+"
        r"with fares starting (?:at|from)\s+"
        r"(?:[A-Za-z]{3}\s+\d{1,2}/\d{1,2}\s+)?"
        r"(?P<miles>[\d.,]+k?)\s+miles(?:\s+miles)?\s*"
        r"(?:\+\s*plus|\+\s*|plus\s+)?\s*\$?(?P<taxes>\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    target_cabin = cabin.lower().strip() or "economy"
    rows: List[Dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for parsed in calendar_pattern.finditer(normalized):
        depart_date = _parse_united_calendar_date(
            parsed.group("month"),
            parsed.group("day"),
            parsed.group("year"),
        )
        if depart_date is None:
            continue

        miles = _normalize_united_miles(parsed.group("miles"))
        if miles > max_miles:
            continue

        row: Dict[str, Any] = {
            "route": route,
            "date": depart_date.isoformat(),
            "date_label": depart_date.strftime("%b %d"),
            "miles": miles,
            "taxes": parsed.group("taxes"),
            "travelers": travelers,
            "cabin": target_cabin,
            "mixed_cabin": False,
            "source": "united_7day_calendar",
            "notes": "7-day calendar starting fare",
        }
        key = (row["date"], row["miles"], row["taxes"], row["cabin"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    return rows


def _extract_united_matches_from_text(
    text: str,
    *,
    route: str,
    depart_date: date,
    travelers: int,
    cabin: str,
    max_miles: int,
) -> List[Dict[str, Any]]:
    if not text:
        return []

    fare_pattern = re.compile(
        r"(?P<miles>[\d.,]+k?)\s*miles\s*\+\s*\$(?P<taxes>\d+(?:\.\d{1,2})?)\s*"
        r"(?P<notes>.*?)Select fare for (?P<label>Economy|Premium Economy|Business \(lowest\))",
        re.IGNORECASE | re.DOTALL,
    )

    target_cabin = cabin.lower().strip()
    rows: List[Dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for parsed in fare_pattern.finditer(text):
        label = parsed.group("label").strip().lower()
        if "business" in label:
            detected_cabin = "business"
        elif "premium" in label:
            detected_cabin = "premium_economy"
        else:
            detected_cabin = "economy"

        if target_cabin and detected_cabin != target_cabin:
            continue

        miles = _normalize_united_miles(parsed.group("miles"))
        if miles > max_miles:
            continue

        notes_text = " ".join(parsed.group("notes").replace("\xa0", " ").split())
        mixed_cabin = "mixed cabin" in notes_text.lower()
        carrier = "United" if "united" in notes_text.lower() or "polaris" in notes_text.lower() else ""

        row: Dict[str, Any] = {
            "route": route,
            "date": depart_date.isoformat(),
            "date_label": depart_date.strftime("%b %d"),
            "miles": miles,
            "taxes": parsed.group("taxes"),
            "travelers": travelers,
            "cabin": detected_cabin,
            "mixed_cabin": mixed_cabin,
            "source": "united_result_text",
        }
        if carrier:
            row["carrier"] = carrier
        if notes_text:
            row["notes"] = notes_text

        key = (
            row["date"],
            row["miles"],
            row["taxes"],
            row["cabin"],
            row["mixed_cabin"],
            row.get("notes", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    return rows


def _filter_united_matches(
    matches: List[Dict[str, Any]],
    *,
    cabin: str,
    allow_mixed: bool,
) -> List[Dict[str, Any]]:
    target_cabin = cabin.lower().strip()
    filtered: List[Dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in matches:
        detected_cabin = str(row.get("cabin", "")).lower().strip()
        if target_cabin and detected_cabin and detected_cabin != target_cabin:
            continue
        if not allow_mixed and bool(row.get("mixed_cabin")):
            continue
        key = (
            row.get("date"),
            row.get("miles"),
            row.get("taxes"),
            row.get("cabin"),
            row.get("mixed_cabin", False),
            row.get("source", ""),
            row.get("notes", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        filtered.append(row)

    return filtered


def _configure_united_results_view(page: Any, cabin: str, observations: List[str]) -> Dict[str, bool]:
    target_cabin = cabin.lower().strip()
    applied = {"sorted": False, "mixed_hidden": False}
    if target_cabin not in {"business", "first"}:
        return applied

    label = "Business" if target_cabin == "business" else "First"
    if _try_click_any(
        page,
        [
            f"text=/Select to sort results by {label}/i",
            f"text=/{label}\\s*\\(lowest\\)/i",
            f"button:has-text('{label}')",
            f"[role='button']:has-text('{label}')",
            f"[role='link']:has-text('{label}')",
        ],
        timeout=2000,
    ):
        applied["sorted"] = True
        observations.append(f"United results: requested {label} sort")
        time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass

    if _try_click_any(
        page,
        [
            "button:has-text('Mixed Cabin')",
            "[role='button']:has-text('Mixed Cabin')",
            "[aria-haspopup]:has-text('Mixed Cabin')",
            "text=/Mixed Cabin/i",
        ],
        timeout=2000,
    ):
        time.sleep(1)
        if _try_click_any(
            page,
            [
                "button:has-text('Hide mixed cabin fares')",
                "[role='menuitemradio']:has-text('Hide mixed cabin fares')",
                "[role='button']:has-text('Hide mixed cabin fares')",
                "label:has-text('Hide mixed cabin fares')",
                "text=/Hide mixed cabin fares/i",
            ],
            timeout=2000,
        ):
            applied["mixed_hidden"] = True
            observations.append("United results: hid mixed-cabin fares")
            time.sleep(1)
            try:
                page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
        _try_click_any(
            page,
            [
                "button:has-text('Close dialog')",
                "button[aria-label='Close']",
                "button:has-text('Close')",
            ],
            timeout=1500,
        )
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    return applied


def _finalize_united_result_page(
    page: Any,
    observations: List[str],
    *,
    origin: str,
    dest: str,
    depart_date: date,
    travelers: int,
    cabin: str,
    max_miles: int,
    booking_url: str,
    context_label: str,
) -> Dict[str, Any]:
    if not _page_is_live(page):
        observations.append(f"United {context_label} ended with no live page to parse")
        return {
            "mode": "live",
            "real_data": False,
            "matches": [],
            "booking_url": booking_url,
            "summary": "United award page closed before reliable results could be parsed.",
            "raw_observations": observations,
            "errors": ["No live United page available"],
        }

    state = _page_state(page)
    observations.append(
        "United "
        f"{context_label} page state: "
        f"flight_cards={state['flight_cards']} "
        f"miles_mentions={state['miles_mentions']} "
        f"skeletons={state['skeletons']} "
        f"no_results={state['no_results']}"
    )
    observations.append(f"United current URL: {page.url}")

    view_config = _configure_united_results_view(page, cabin, observations)
    if view_config["sorted"] or view_config["mixed_hidden"]:
        _wait_for_award_results(page, timeout_s=15)

    result_text = _collect_result_text(page)
    allow_mixed = cabin.lower().strip() == "economy"
    calendar_matches = []
    if cabin.lower().strip() in {"business", "first"} and view_config["sorted"]:
        calendar_matches = _extract_united_calendar_matches_from_text(
            result_text,
            route=f"{origin}-{dest}",
            travelers=travelers,
            cabin=cabin,
            max_miles=max_miles,
        )
        if calendar_matches and not view_config["mixed_hidden"]:
            observations.append(
                "United calendar fares found before mixed-cabin hide could be confirmed; discarding them."
            )
            calendar_matches = []

    matches = _extract_united_matches_from_text(
        result_text,
        route=f"{origin}-{dest}",
        depart_date=depart_date,
        travelers=travelers,
        cabin=cabin,
        max_miles=max_miles,
    )
    if not matches and _looks_like_united_results_page(page, state, result_text):
        matches = extract_award_matches_from_text(
            result_text,
            route=f"{origin}-{dest}",
            cabin=cabin,
            travelers=travelers,
            max_miles=max_miles,
        )
    matches = _filter_united_matches(matches, cabin=cabin, allow_mixed=allow_mixed)
    if calendar_matches:
        matches = _filter_united_matches(calendar_matches, cabin=cabin, allow_mixed=False)

    if matches:
        best = min(match["miles"] for match in matches)
        return {
            "mode": "live",
            "real_data": True,
            "matches": matches,
            "booking_url": booking_url,
            "summary": (
                f"United {context_label}: {len(matches)} flight(s) found. "
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
            "booking_url": booking_url,
            "summary": f"United {context_label} completed: no flights found.",
            "raw_observations": observations,
            "errors": [],
        }

    if state["invalid_credentials"]:
        return {
            "mode": "live",
            "real_data": False,
            "matches": [],
            "booking_url": booking_url,
            "summary": "United rejected the provided credentials on the award page.",
            "raw_observations": observations,
            "errors": ["United rejected credentials"],
        }

    observations.append(
        f"United {context_label} loaded a page but did not yield parseable award data"
    )
    observations.extend(_capture_debug_artifacts(page, f"united_{context_label.replace(' ', '_')}_debug"))
    return {
        "mode": "live",
        "real_data": False,
        "matches": [],
        "booking_url": booking_url,
        "summary": "United award page loaded, but the parser could not extract reliable award results.",
        "raw_observations": observations,
        "errors": [],
    }


def _run_homepage_award_search(
    context: Dict[str, Any],
    inputs: Dict[str, Any],
    observations: List[str],
) -> Dict[str, Any] | None:
    del context
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        observations.append("Playwright not available for United homepage path")
        return None

    origin = inputs["from"]
    dest = inputs["to"][0]
    travelers = int(inputs["travelers"])
    cabin = str(inputs.get("cabin", "economy"))
    max_miles = int(inputs["max_miles"])
    depart_date = date.today() + timedelta(days=int(inputs["days_ahead"]))
    award_url = _booking_url(origin, dest, depart_date, cabin, travelers, award=True)
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222").strip() or "http://127.0.0.1:9222"

    created_page = False
    page: Any | None = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context_pw, _existing_page = _select_cdp_context(browser)
            if context_pw is None:
                observations.append("United homepage path found no usable CDP browser contexts")
                return None

            try:
                page = context_pw.new_page()
                created_page = True
                observations.append("United homepage path opened a fresh page in the persistent CDP context")
            except Exception as exc:
                observations.append(f"United homepage path could not open a fresh page: {exc}")
                page = _active_united_page(context_pw)
                if _page_is_live(page):
                    observations.append("United homepage path reusing an existing live page")
            if not _page_is_live(page):
                observations.append(
                    "United homepage path found no reusable page in the selected CDP context: "
                    + " | ".join(_page_inventory(context_pw))
                )
                return None

            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(30000)
            observations.append("United trying deterministic homepage award search first")
            if not _submit_homepage_award_search(
                page,
                origin,
                dest,
                depart_date,
                cabin,
                travelers,
                observations,
            ):
                return None
            return _finalize_united_result_page(
                page,
                observations,
                origin=origin,
                dest=dest,
                depart_date=depart_date,
                travelers=travelers,
                cabin=cabin,
                max_miles=max_miles,
                booking_url=award_url,
                context_label="homepage search",
            )
    except Exception as exc:
        observations.append(f"United homepage path failed before a reliable result: {exc}")
        return None
    finally:
        # CDP-attached United results pages can hang on close(); prefer reliability
        # and prune stale tabs before later runs instead of forcing teardown here.
        pass


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

    otp_inputs = page.locator("input.atm-c-otp-input, input[inputmode='numeric']")
    otp_digit_inputs: list[Any] = []
    try:
        count = otp_inputs.count()
    except Exception:
        count = 0
    for idx in range(min(count, 6)):
        candidate = otp_inputs.nth(idx)
        try:
            if candidate.is_visible():
                otp_digit_inputs.append(candidate)
        except Exception:
            continue

    code_input = _first_visible(
        [
            page.get_by_label(re.compile(r"(verification|security|one-time).*(code|passcode)", re.IGNORECASE)),
            page.get_by_label(re.compile(r"enter digit \\d+ of 6", re.IGNORECASE)),
            page.get_by_label(re.compile(r"enter code", re.IGNORECASE)),
            page.locator("input[autocomplete='one-time-code']"),
            page.locator("input[name*='code']"),
            page.locator("input[id*='code']"),
        ]
    )
    if not code_input and len(otp_digit_inputs) < 6:
        return True, ""

    observations.append("United requested SMS 2FA")
    since_ts = time.time() - 60
    code = read_sms_code(
        sender=UNITED_SMS_SENDER,
        keyword=None,
        since_timestamp=since_ts,
        timeout=90,
    )
    if not code:
        return False, "United 2FA requested but no code was received"
    code = str(code).strip()

    if len(otp_digit_inputs) >= 6:
        for idx, digit in enumerate(code[:6]):
            if not _fill(otp_digit_inputs[idx], digit):
                try:
                    otp_digit_inputs[idx].type(digit, delay=50)
                except Exception:
                    return False, "Failed to enter United 2FA code digits"
    elif not _fill(code_input, code):
        return False, "Failed to enter United 2FA code"

    remember_device = _first_visible(
        [
            page.get_by_role("checkbox", name=re.compile(r"remember this browser", re.IGNORECASE)),
            page.get_by_label(re.compile(r"remember this browser", re.IGNORECASE)),
            page.locator("input[name='rememberDevice']"),
        ]
    )
    if remember_device:
        try:
            if not remember_device.is_checked():
                remember_device.check(timeout=3000)
        except Exception:
            _click(remember_device, timeout=1500)

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


def _ensure_united_login(
    page: Any,
    browser: Any,
    context_pw: Any,
    context: Dict[str, Any],
    observations: List[str],
) -> tuple[Any, bool, str]:
    username, password = _resolve_united_credentials(context)
    if not username or not password:
        return page, False, "United credentials are unavailable"

    def refresh(wait_s: float = 0.0, timeout_s: float = 8.0) -> Any:
        nonlocal page
        nonlocal context_pw
        if wait_s > 0:
            time.sleep(wait_s)
        context_pw, page = _wait_for_active_united_page_in_browser(
            browser,
            current_context=context_pw,
            current_page=page,
            timeout_s=timeout_s,
        )
        if page is None:
            observations.append(
                "United login lost all live CDP pages; inventory: "
                + " | ".join(_browser_page_inventory(browser))
            )
        return page

    if not _page_is_live(page):
        return page, False, "United login started without a live page"

    _dismiss_united_overlays(page)
    modal_visible = _is_sign_in_visible(page)

    if not modal_visible and _needs_miles_sign_in(page):
        sign_in_for_miles = _first_visible(
            [
                page.locator("button:has-text('Sign In')").last,
                page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)).last,
            ]
        )
        if sign_in_for_miles:
            _click(sign_in_for_miles)
            refresh(2, timeout_s=10)
            if not _page_is_live(page):
                return page, False, "United miles sign-in closed the active page"
            observations.append("United required an extra sign-in for miles pricing")
            modal_visible = _is_sign_in_visible(page)

    if _needs_miles_sign_in(page) and not modal_visible:
        return page, False, "United still requires sign-in to view miles results"

    if _looks_logged_in(page) and not modal_visible:
        observations.append("United already logged in")
        return page, True, ""

    if not modal_visible:
        sign_in_cta = _first_visible(
            [
                page.get_by_role("link", name=re.compile(r"^sign in$", re.IGNORECASE)).last,
                page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)).last,
            ]
        )
        if sign_in_cta:
            _click(sign_in_cta)
            refresh(2, timeout_s=10)
            if not _page_is_live(page):
                return page, False, "United sign-in CTA closed the active page"
            modal_visible = _is_sign_in_visible(page)

    if not modal_visible:
        if not _page_is_live(page):
            return page, False, "United sign-in dismissed but no live page remained"
        return page, True, ""

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
            return page, False, "Failed to enter United username"

    password_input = _first_visible(
        [
            page.get_by_label(re.compile(r"password", re.IGNORECASE)),
            page.locator("input[type='password']"),
            page.locator("input[autocomplete='current-password']"),
        ]
    )
    switch_accounts = _first_visible(
        [
            page.get_by_role("button", name=re.compile(r"switch accounts", re.IGNORECASE)),
            page.locator("button:has-text('Switch accounts')"),
        ]
    )
    used_switch_accounts = False

    if not username_input and not password_input and switch_accounts:
        _click(switch_accounts)
        refresh(2, timeout_s=10)
        if not _page_is_live(page):
            return page, False, "United switch-accounts step closed the active page"
        observations.append("United login required 'Switch accounts'")
        used_switch_accounts = True
        username_input = _first_visible(
            [
                page.get_by_label(re.compile(r"mileageplus.*number", re.IGNORECASE)),
                page.locator("input[autocomplete='username']"),
                page.locator("input[name*='user']"),
                page.locator("input[id*='user']"),
            ]
        )
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
        refresh(2, timeout_s=10)
        if not _page_is_live(page):
            return page, False, "United continue step closed the active page"
        password_input = _first_visible(
            [
                page.get_by_label(re.compile(r"password", re.IGNORECASE)),
                page.locator("input[type='password']"),
                page.locator("input[autocomplete='current-password']"),
            ]
        )

    if not password_input and not used_switch_accounts and switch_accounts:
        _click(switch_accounts)
        refresh(2, timeout_s=10)
        if not _page_is_live(page):
            return page, False, "United switch-accounts fallback closed the active page"
        observations.append("United login fell back to 'Switch accounts'")
        used_switch_accounts = True
        username_input = _first_visible(
            [
                page.get_by_label(re.compile(r"mileageplus.*number", re.IGNORECASE)),
                page.locator("input[autocomplete='username']"),
                page.locator("input[name*='user']"),
                page.locator("input[id*='user']"),
            ]
        )
        if username_input and not _fill(username_input, username):
            return page, False, "Failed to enter United username after switch-accounts fallback"
        password_input = _first_visible(
            [
                page.get_by_label(re.compile(r"password", re.IGNORECASE)),
                page.locator("input[type='password']"),
                page.locator("input[autocomplete='current-password']"),
            ]
        )

    if not password_input:
        return page, False, "United password field was not visible"
    if not _fill(password_input, password):
        return page, False, "Failed to enter United password"

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
            page.locator("button[type='submit']").last,
            page.locator("button:has-text('Sign in')").last,
            page.get_by_role("button", name=re.compile(r"^sign in$", re.IGNORECASE)).last,
        ]
    )
    if not sign_in_btn:
        return page, False, "United sign-in button was not visible"

    _click(sign_in_btn)
    refresh(4, timeout_s=12)
    if not _page_is_live(page):
        return page, False, "United sign-in closed the active page before completion"

    otp_ok, otp_error = _submit_united_otp(page, observations)
    if not otp_ok:
        return page, False, otp_error

    if _page_state(page)["invalid_credentials"]:
        return page, False, "United rejected the provided credentials"

    for _ in range(20):
        refresh(1, timeout_s=4)
        if not _page_is_live(page):
            return page, False, "United login ended with no live page available"
        if _looks_logged_in(page) and not _is_sign_in_visible(page):
            return page, True, ""
        if _needs_miles_sign_in(page) and not _is_sign_in_visible(page):
            return page, False, "United still requires sign-in to view miles results"
        if not _is_sign_in_visible(page):
            return page, True, ""

    return page, False, "United sign-in modal remained visible"


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
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222").strip() or "http://127.0.0.1:9222"

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context_pw, existing_page = _select_cdp_context(browser)
            if context_pw is None:
                observations.append("Direct United path found no usable CDP browser contexts")
                return None

            def reconnect_after_login() -> tuple[Any | None, Any | None, Any | None]:
                fresh_browser = p.chromium.connect_over_cdp(cdp_url)
                fresh_context, fresh_page = _select_cdp_context(fresh_browser)
                if fresh_context is not None:
                    observations.append("United direct path refreshed the CDP connection after login attempt")
                return fresh_browser, fresh_context, fresh_page

            page = existing_page
            created_page = False
            try:
                page = context_pw.new_page()
                created_page = True
                observations.append("Direct United path opened a fresh page in the persistent CDP context")
            except Exception as exc:
                observations.append(f"Fresh CDP page unavailable in selected context: {exc}")
                page = existing_page or _active_united_page(context_pw)
                if page is not None:
                    observations.append("Direct United path reusing an existing live page after fresh-page failure")
            if not _page_is_live(page):
                observations.append(
                    "Direct United path found no reusable page in the selected CDP context: "
                    + " | ".join(_page_inventory(context_pw))
                )
                return None

            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(30000)
            if _goto_with_retry(page, UNITED_URL, observations, attempts=2):
                time.sleep(3)
                _dismiss_united_overlays(page)
                observations.append("United trying deterministic homepage award search first")
                if _submit_homepage_award_search(
                    page,
                    origin,
                    dest,
                    depart_date,
                    cabin,
                    travelers,
                    observations,
                ):
                    homepage_result = _finalize_united_result_page(
                        page,
                        observations,
                        origin=origin,
                        dest=dest,
                        depart_date=depart_date,
                        travelers=travelers,
                        cabin=cabin,
                        max_miles=max_miles,
                        booking_url=award_url,
                        context_label="homepage search",
                    )
                    if homepage_result.get("real_data"):
                        return homepage_result
                    observations.append(
                        "United homepage-first search did not yield reliable data; retrying via direct award URL"
                    )
            if not _goto_with_retry(page, award_url, observations):
                return None
            time.sleep(4)
            observations.append(f"Direct United award URL: {award_url}")

            page, logged_in, login_error = _ensure_united_login(
                page,
                browser,
                context_pw,
                context,
                observations,
            )
            if logged_in or "live page" in login_error.lower():
                try:
                    fresh_browser, fresh_context, fresh_page = reconnect_after_login()
                    if fresh_context is not None:
                        browser = fresh_browser
                        context_pw = fresh_context
                        page = fresh_page
                except Exception as exc:
                    observations.append(f"United CDP reconnect after login failed: {exc}")

            if _page_is_live(page) and _is_sign_in_visible(page):
                otp_ok, otp_error = _submit_united_otp(page, observations)
                if not otp_ok:
                    login_error = otp_error
                    logged_in = False
                else:
                    try:
                        fresh_browser, fresh_context, fresh_page = reconnect_after_login()
                        if fresh_context is not None:
                            browser = fresh_browser
                            context_pw = fresh_context
                            page = fresh_page
                    except Exception as exc:
                        observations.append(f"United CDP reconnect after OTP failed: {exc}")

            if _page_is_live(page):
                if _needs_miles_sign_in(page) and not _is_sign_in_visible(page):
                    logged_in = False
                    login_error = "United still requires sign-in to view miles results"
                elif not _is_sign_in_visible(page):
                    logged_in = True
                    login_error = ""

            if not logged_in:
                if "still requires sign-in to view miles results" in login_error.lower():
                    observations.append(
                        "United direct award URL kept the miles sign-in gate; retrying via homepage search"
                    )
                    if not _page_is_live(page):
                        context_pw, page = _wait_for_active_united_page_in_browser(
                            browser,
                            current_context=context_pw,
                            current_page=page,
                            timeout_s=8,
                        )
                        if not _page_is_live(page):
                            try:
                                page = context_pw.new_page()
                                created_page = True
                                observations.append(
                                    "United homepage fallback reopened a fresh page after direct miles gate"
                                )
                            except Exception as exc:
                                observations.append(
                                    f"United homepage fallback could not open a new page: {exc}"
                                )
                    if _page_is_live(page) and _submit_homepage_award_search(
                        page,
                        origin,
                        dest,
                        depart_date,
                        cabin,
                        travelers,
                        observations,
                    ):
                        return _finalize_united_result_page(
                            page,
                            observations,
                            origin=origin,
                            dest=dest,
                            depart_date=depart_date,
                            travelers=travelers,
                            cabin=cabin,
                            max_miles=max_miles,
                            booking_url=award_url,
                            context_label="homepage fallback",
                        )
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

            context_pw, page = _wait_for_active_united_page_in_browser(
                browser,
                current_context=context_pw,
                current_page=page,
                timeout_s=12,
            )
            if not _page_is_live(page):
                try:
                    page = context_pw.new_page()
                    created_page = True
                    observations.append("United direct path reopened a fresh page after results target loss")
                except Exception as exc:
                    observations.append(f"United could not reopen a page after results target loss: {exc}")
            if not _page_is_live(page):
                observations.append("United login completed but no live page remained in the CDP context")
                observations.append(
                    "United page inventory after login: " + " | ".join(_browser_page_inventory(browser))
                )
                return None
            if not _goto_with_retry(page, award_url, observations):
                return None
            _wait_for_award_results(page, timeout_s=25)
            if not _page_is_live(page):
                context_pw, page = _wait_for_active_united_page_in_browser(
                    browser,
                    current_context=context_pw,
                    current_page=page,
                    timeout_s=8,
                )
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
                    return _finalize_united_result_page(
                        page,
                        observations,
                        origin=origin,
                        dest=dest,
                        depart_date=depart_date,
                        travelers=travelers,
                        cabin=cabin,
                        max_miles=max_miles,
                        booking_url=award_url,
                        context_label="homepage fallback",
                    )
            return _finalize_united_result_page(
                page,
                observations,
                origin=origin,
                dest=dest,
                depart_date=depart_date,
                travelers=travelers,
                cabin=cabin,
                max_miles=max_miles,
                booking_url=award_url,
                context_label="direct award search",
            )
    except Exception as exc:
        observations.append(f"Direct United path failed before a reliable result: {exc}")
        return None
    finally:
        # CDP-attached United results pages can hang on close(); prefer reliability
        # and prune stale tabs before later runs instead of forcing teardown here.
        pass


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

    homepage_result = _run_homepage_award_search(context, inputs, observations)
    if homepage_result is not None:
        return homepage_result

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
