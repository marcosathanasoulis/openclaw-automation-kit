from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class ParsedQuery:
    script_dir: str
    inputs: Dict[str, object]
    notes: List[str]


AIRLINE_TO_SCRIPT = {
    "united": "library/united_award",
    "singapore": "library/singapore_award",
    "singapore air": "library/singapore_award",
    "singapore airlines": "library/singapore_award",
    "krisflyer": "library/singapore_award",
    "sia": "library/singapore_award",
    "sq": "library/singapore_award",
    "ana": "library/ana_award",
    "all nippon": "library/ana_award",
    "delta": "library/delta_award",
    "aeromexico": "library/aeromexico_award",
    "aero mexico": "library/aeromexico_award",
    "jetblue": "library/jetblue_award",
    "jet blue": "library/jetblue_award",
    "chase": "library/chase_balance",
    "bank of america": "library/bofa_alert",
    "bofa": "library/bofa_alert",
    "boa": "library/bofa_alert",
    "github login": "library/github_signin_check",
    "github signin": "library/github_signin_check",
    "github": "library/github_signin_check",
}

KNOWN_AIRPORT_CODES = {
    "AMS", "ATH", "BKK", "BOS", "CDG", "DEN", "DFW", "EWR", "EZE",
    "FCO", "FRA", "GIG", "GRU", "HKG", "HND", "IAD", "IAH", "ICN",
    "JFK", "KIX", "LAX", "LHR", "LIS", "MEX", "MIA", "MSP", "NRT",
    "ORD", "PEK", "PVG", "SEA", "SFO", "SIN", "SYD", "TPE", "YVR",
    "YYZ", "ZRH",
}

COMMON_THREE_LETTER_WORDS = {
    "ANA", "THE", "AND", "FOR", "ONE", "TWO", "ALL", "ANY", "NOT",
    "BUT", "HAS", "HAD", "HER", "HIS", "HOW", "ITS", "LET", "MAY",
    "NEW", "NOW", "OLD", "OUR", "OUT", "OWN", "SAY", "SHE", "TOO",
    "USE", "WAY", "WHO", "BOY", "DID", "GET", "HIM", "MAN", "RUN",
    "DAY", "FLY", "MAX", "VIA",
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def _detect_script_dir(query: str) -> str:
    q = query.lower()
    has_url = re.search(r"https?://", query) is not None
    if not has_url and any(token in q for token in ["meeting", "meetings", "calendar", "gmail", "email", "emails", "inbox"]):
        return "examples/google_workspace_brief"
    if "weather" in q and not has_url:
        return "examples/weather_check"
    if has_url:
        return "examples/public_page_check"
    if "home page" in q or "homepage" in q:
        return "examples/public_page_check"
    for token, script_dir in AIRLINE_TO_SCRIPT.items():
        if token in q:
            return script_dir
    return "examples/public_page_check"


def _extract_url(query: str) -> str | None:
    url_match = re.search(r"https?://[^\s\"']+", query)
    if not url_match:
        return None
    return url_match.group(0).rstrip(".,;:!?")


def _extract_keyword(query: str, default: str = "news") -> str:
    quoted = re.search(r"\"([^\"]{2,80})\"", query)
    if quoted:
        return quoted.group(1).strip()

    patterns = [
        r"(?:mentions?|count|times?)\s+of\s+([a-zA-Z][a-zA-Z0-9_\-\s]{1,60})",
        r"check\s+(?:if\s+)?([a-zA-Z][a-zA-Z0-9_\-\s]{1,60})\s+(?:is|exists|appears)",
        r"contains?\s+([a-zA-Z][a-zA-Z0-9_\-\s]{1,60})",
        r"about\s+([a-zA-Z][a-zA-Z0-9_\-\s]{1,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;!?")
            if candidate:
                return candidate
    return default


def _extract_public_task(query: str) -> str:
    q = query.lower()
    if any(token in q for token in ["headline", "headlines", "top stories", "top news"]):
        return "headlines"
    if any(token in q for token in ["summarize", "summary", "what is this page about"]):
        return "summary"
    return "keyword_count"


def _extract_weather_location(query: str) -> str:
    match = re.search(r"\bweather\s+(?:in|for)\s+([a-zA-Z0-9,\-\s]{2,80})", query, flags=re.IGNORECASE)
    if match:
        location = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;!?")
        location = re.sub(
            r"\b(in\s+)?(celsius|fahrenheit|centigrade)\b$", "", location, flags=re.IGNORECASE
        ).strip(" .,:;!?")
        if location:
            return location
    return "San Francisco, CA"


def _extract_weather_unit(query: str) -> str:
    q = query.lower()
    if "celsius" in q or "centigrade" in q:
        return "celsius"
    return "fahrenheit"


def _extract_workspace_task(query: str) -> str:
    q = query.lower()
    wants_meetings = any(token in q for token in ["meeting", "meetings", "calendar", "schedule"])
    wants_emails = any(token in q for token in ["email", "emails", "gmail", "inbox"])
    if wants_meetings and wants_emails:
        return "brief"
    if wants_emails:
        return "emails"
    return "meetings"


def _extract_workspace_email_query(query: str) -> str:
    q = query.lower().strip()
    skip_sender_terms = {"gmail", "email", "emails", "inbox", "mail"}

    explicit_from = re.search(r"\bfrom\s+([a-z0-9._%+\-@]+)\b", q)
    if explicit_from:
        sender = explicit_from.group(1).strip(" .,:;!?")
        if sender and sender not in skip_sender_terms:
            return f"from:{sender}"

    last_time = re.search(r"last time\s+([a-z0-9._%+\-\s]+?)\s+email(?:ed)?\s+me", q)
    if last_time:
        sender = re.sub(r"\s+", " ", last_time.group(1)).strip(" .,:;!?")
        if sender and sender not in skip_sender_terms:
            return f"from:{sender}"

    return "newer_than:7d"


def _extract_workspace_max_results(query: str, task: str) -> int:
    q = query.lower()
    if task == "emails" and "last time" in q:
        return 1
    m = re.search(r"\b(last|latest)\s+(\d+)\s+(emails?|messages?)\b", q)
    if m:
        return max(1, min(int(m.group(2)), 50))
    return 10


def _next_or_same_weekday(target_weekday: int) -> date:
    today = date.today()
    delta = (target_weekday - today.weekday()) % 7
    return today + timedelta(days=delta)


def _next_weekday(target_weekday: int) -> date:
    today = date.today()
    delta = (target_weekday - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _extract_workspace_date(query: str) -> str:
    q = query.lower()
    if "tomorrow" in q:
        return (date.today() + timedelta(days=1)).isoformat()
    if "today" in q:
        return date.today().isoformat()

    explicit = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", q)
    if explicit:
        return explicit.group(1)

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for day_name, weekday_num in weekdays.items():
        if f"next {day_name}" in q:
            return _next_weekday(weekday_num).isoformat()
        if day_name in q:
            return _next_or_same_weekday(weekday_num).isoformat()

    return date.today().isoformat()


def _extract_airport_codes(query: str) -> List[str]:
    codes = re.findall(r"\b[A-Z]{3}\b", query)
    known = [code for code in codes if code in KNOWN_AIRPORT_CODES]
    if known:
        return known
    return [code for code in codes if code not in COMMON_THREE_LETTER_WORDS]


def _extract_travelers(query: str) -> int:
    match = re.search(r"\b(\d+)\s*(people|traveler|travelers|adults?|pax|passengers?)\b", query.lower())
    if match:
        return int(match.group(1))
    if "two" in query.lower():
        return 2
    return 1


def _extract_days_ahead(query: str) -> int:
    # "next N days"
    m = re.search(r"(next|within)\s+(\d+)\s+days", query.lower())
    if m:
        return max(1, min(int(m.group(2)), 365))

    # "in June", "in March", month names
    q = query.lower()
    for month_name, month_num in MONTH_NAMES.items():
        if f"in {month_name}" in q or f"for {month_name}" in q or f"during {month_name}" in q:
            today = date.today()
            target_year = today.year
            # If the month is in the past, assume next year
            if month_num < today.month:
                target_year += 1
            elif month_num == today.month and today.day > 15:
                target_year += 1
            target_date = date(target_year, month_num, 15)
            days = (target_date - today).days
            return max(1, min(days + 15, 365))  # cover the whole month

    # "next week"
    if "next week" in q:
        return 14

    return 30


def _extract_max_miles(query: str) -> int:
    m = re.search(r"(?:<=|under|below|max|at)\s*(\d+)\s*k?\s*miles", query.lower())
    if m:
        value = int(m.group(1))
        if value < 1000:
            value *= 1000
        return value
    return 120000


def _extract_cabin(query: str) -> str:
    q = query.lower()
    if "economy" in q:
        return "economy"
    if "business" in q:
        return "business"
    if "first" in q:
        return "first"
    if "premium" in q:
        return "premium_economy"
    return "economy"


def parse_query_to_run(query: str) -> ParsedQuery:
    script_dir = _detect_script_dir(query)
    airports = _extract_airport_codes(query)
    travelers = _extract_travelers(query)
    days_ahead = _extract_days_ahead(query)
    max_miles = _extract_max_miles(query)
    cabin = _extract_cabin(query)

    from_code = airports[0] if airports else "SFO"
    to_codes = airports[1:] if len(airports) > 1 else ["AMS"]
    notes = [f"script={script_dir}", f"cabin={cabin}"]

    inputs: Dict[str, object]
    if script_dir == "examples/public_page_check":
        url = _extract_url(query) or "https://www.yahoo.com"
        keyword = _extract_keyword(query, default="news")
        task = _extract_public_task(query)
        inputs = {"url": url, "keyword": keyword, "task": task}
        notes = [f"script={script_dir}", f"url={url}", f"keyword={keyword}", f"task={task}"]
    elif script_dir == "examples/weather_check":
        location = _extract_weather_location(query)
        temperature_unit = _extract_weather_unit(query)
        inputs = {"location": location, "temperature_unit": temperature_unit}
        notes = [f"script={script_dir}", f"location={location}", f"temperature_unit={temperature_unit}"]
    elif script_dir == "examples/google_workspace_brief":
        task = _extract_workspace_task(query)
        target_date = _extract_workspace_date(query)
        gmail_query = _extract_workspace_email_query(query)
        max_results = _extract_workspace_max_results(query, task)
        inputs = {
            "task": task,
            "date": target_date,
            "max_results": max_results,
            "gmail_query": gmail_query,
        }
        notes = [
            f"script={script_dir}",
            f"task={task}",
            f"date={target_date}",
            "account_scope=all_allowlisted",
            f"gmail_query={gmail_query}",
            f"max_results={max_results}",
        ]
    elif "award" in script_dir:
        inputs = {
            "from": from_code,
            "to": to_codes,
            "days_ahead": days_ahead,
            "max_miles": max_miles,
            "travelers": travelers,
            "cabin": cabin,
        }
    else:
        inputs = {"query": query}

    return ParsedQuery(script_dir=script_dir, inputs=inputs, notes=notes)


def resolve_script_dir(root: Path, script_dir: str) -> Path:
    return (root / script_dir).resolve()
