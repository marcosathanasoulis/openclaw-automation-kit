from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

_MATCH_LINE = re.compile(
    r"^MATCH\|(?P<date>\d{4}-\d{2}-\d{2}|unknown)\|(?P<miles>\d{2,6})\|(?P<taxes>[0-9.]+|unknown)"
    r"(?:\|(?P<stops>[^|]*))?(?:\|(?P<carrier>[^|]*))?(?:\|(?P<notes>.*))?$",
    re.IGNORECASE,
)


def _parse_match_lines(
    text: str,
    *,
    route: str,
    cabin: str,
    travelers: int,
    max_miles: int,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for line in text.splitlines():
        parsed = _MATCH_LINE.match(line.strip())
        if not parsed:
            continue
        miles = int(parsed.group("miles"))
        if miles > max_miles:
            continue
        taxes = parsed.group("taxes")
        row: Dict[str, Any] = {
            "route": route,
            "date": parsed.group("date"),
            "miles": miles,
            "taxes": taxes if taxes.lower() != "unknown" else "",
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "source": "match_line",
        }
        stops = (parsed.group("stops") or "").strip()
        carrier = (parsed.group("carrier") or "").strip()
        notes = (parsed.group("notes") or "").strip()
        if stops:
            row["stops"] = stops
        if carrier:
            row["carrier"] = carrier
        if notes:
            row["notes"] = notes
        matches.append(row)
    return matches


def extract_award_matches_from_text(
    text: str,
    *,
    route: str,
    cabin: str,
    travelers: int,
    max_miles: int,
) -> List[Dict[str, Any]]:
    """Best-effort parse of miles/tax rows from freeform agent text."""
    if not text:
        return []

    structured = _parse_match_lines(
        text,
        route=route,
        cabin=cabin,
        travelers=travelers,
        max_miles=max_miles,
    )
    if structured:
        return structured

    current_year = datetime.now().year
    matches: List[Dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<label>[A-Za-z]{3}\s+\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})[:\-\s]+"
        r"(?P<miles>\d+(?:\.\d+)?)k?\s*miles?\s*\+\s*\$(?P<taxes>\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    for parsed in pattern.finditer(text):
        label = parsed.group("label").strip()
        raw_miles = parsed.group("miles")
        miles = int(float(raw_miles) * (1000 if "." in raw_miles or float(raw_miles) < 1000 else 1))
        if miles > max_miles:
            continue
        taxes = parsed.group("taxes")
        date_iso = ""
        month_day = re.search(r"(\d{1,2})/(\d{1,2})", label)
        if month_day:
            month = int(month_day.group(1))
            day = int(month_day.group(2))
            date_iso = f"{current_year:04d}-{month:02d}-{day:02d}"
        matches.append(
            {
                "route": route,
                "date": date_iso or label,
                "date_label": label,
                "miles": miles,
                "taxes": taxes,
                "travelers": travelers,
                "cabin": cabin,
                "mixed_cabin": False,
                "source": "parsed_from_agent_text",
            }
        )

    if matches:
        return matches

    # Last resort: match standalone miles values for high-cost cases.
    for parsed in re.finditer(r"(?P<miles>\d{2,3}(?:,\d{3})?)\s*miles", text, re.IGNORECASE):
        miles = int(parsed.group("miles").replace(",", ""))
        if miles > max_miles:
            continue
        matches.append(
            {
                "route": route,
                "date": "unknown",
                "date_label": "",
                "miles": miles,
                "taxes": "",
                "travelers": travelers,
                "cabin": cabin,
                "mixed_cabin": False,
                "source": "parsed_miles_only",
            }
        )

    return matches
