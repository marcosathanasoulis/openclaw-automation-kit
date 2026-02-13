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
    "united": "examples/united_award",
    "singapore": "examples/singapore_award",
    "singapore air": "examples/singapore_award",
    "ana": "examples/ana_award",
}


def _detect_script_dir(query: str) -> str:
    q = query.lower()
    for token, script_dir in AIRLINE_TO_SCRIPT.items():
        if token in q:
            return script_dir
    return "examples/united_award"


def _extract_airport_codes(query: str) -> List[str]:
    codes = re.findall(r"\b[A-Z]{3}\b", query)
    excluded = {"ANA"}
    return [code for code in codes if code not in excluded]


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
    if "award" in script_dir:
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
