from __future__ import annotations

import re
from dataclasses import dataclass
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
    "sq": "library/singapore_award",
    "ana": "library/ana_award",
    "bank of america": "library/bofa_alert",
    "bofa": "library/bofa_alert",
    "boa": "library/bofa_alert",
    "github login": "library/github_signin_check",
    "github signin": "library/github_signin_check",
    "github": "library/github_signin_check",
}

KNOWN_AIRPORT_CODES = {
    "AMS",
    "ATH",
    "BKK",
    "CDG",
    "EZE",
    "FCO",
    "FRA",
    "GIG",
    "GRU",
    "HND",
    "LHR",
    "LIS",
    "MEX",
    "NRT",
    "SFO",
    "SIN",
}

COMMON_THREE_LETTER_WORDS = {
    "ANA",
    "THE",
    "AND",
    "FOR",
    "ONE",
    "TWO",
    "ALL",
    "ANY",
    "NOT",
    "BUT",
    "HAS",
    "HAD",
    "HER",
    "HIS",
    "HOW",
    "ITS",
    "LET",
    "MAY",
    "NEW",
    "NOW",
    "OLD",
    "OUR",
    "OUT",
    "OWN",
    "SAY",
    "SHE",
    "TOO",
    "USE",
    "WAY",
    "WHO",
    "BOY",
    "DID",
    "GET",
    "HIM",
    "MAN",
    "RUN",
    "DAY",
    "FLY",
    "MAX",
    "VIA",
}


def _detect_script_dir(query: str) -> str:
    q = query.lower()
    has_url = re.search(r"https?://", query) is not None
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


def _extract_airport_codes(query: str) -> List[str]:
    codes = re.findall(r"\b[A-Z]{3}\b", query)
    known = [code for code in codes if code in KNOWN_AIRPORT_CODES]
    if known:
        return known
    return [code for code in codes if code not in COMMON_THREE_LETTER_WORDS]


def _extract_travelers(query: str) -> int:
    match = re.search(r"\b(\d+)\s*(people|traveler|travelers|adults?)\b", query.lower())
    if match:
        return int(match.group(1))
    return 1


def _extract_days_ahead(query: str) -> int:
    m = re.search(r"(next|within)\s+(\d+)\s+days", query.lower())
    if m:
        return max(1, min(int(m.group(2)), 90))
    return 30


def _extract_max_miles(query: str) -> int:
    m = re.search(r"(?:<=|under|below|max)\s*(\d+)\s*k?\s*miles", query.lower())
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
        inputs = {"url": url, "keyword": keyword}
        notes = [f"script={script_dir}", f"url={url}", f"keyword={keyword}"]
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

