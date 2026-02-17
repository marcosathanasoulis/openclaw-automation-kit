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


def _normalize_miles(raw: str) -> int:
    """Convert various miles formats to integer.

    Handles: '39.8k', '39,800', '300k', '185000', '185,000', '39.8'
    """
    raw = raw.strip().lower().replace(",", "")
    if raw.endswith("k"):
        return int(float(raw[:-1]) * 1000)
    val = float(raw)
    if val < 1000:
        return int(val * 1000)
    return int(val)


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

    # Try structured MATCH| lines first
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

    # Pattern 1: "Xk miles + $Y.ZZ" with optional date label
    # e.g. "Fri 2/20: 39.8k miles + $5.60" or "2/20: 55k miles + $24.80"
    pattern1 = re.compile(
        r"(?P<label>[A-Za-z]{3}\s+\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})[:\-\s]+"
        r"(?P<miles>\d+(?:\.\d+)?)k?\s*miles?\s*\+\s*\$(?P<taxes>\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    for parsed in pattern1.finditer(text):
        label = parsed.group("label").strip()
        miles = _normalize_miles(parsed.group("miles"))
        if miles > max_miles:
            continue
        date_iso = ""
        month_day = re.search(r"(\d{1,2})/(\d{1,2})", label)
        if month_day:
            month = int(month_day.group(1))
            day = int(month_day.group(2))
            date_iso = f"{current_year:04d}-{month:02d}-{day:02d}"
        matches.append({
            "route": route,
            "date": date_iso or label,
            "date_label": label,
            "miles": miles,
            "taxes": parsed.group("taxes"),
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "source": "parsed_from_agent_text",
        })

    if matches:
        return matches

    # Pattern 2: Date strip without taxes — "Fri 2/20: 39.8k miles"
    # Also matches "- Fri 2/20: 39.8k miles" and "Mon 2/23: 47.1k miles (selected date)"
    pattern2 = re.compile(
        r"(?:^|\n)\s*[-•*]?\s*"
        r"(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*\s+)?"
        r"(?P<month>\d{1,2})/(?P<day>\d{1,2})"
        r"[:\s]+(?P<miles>[\d,.]+)k?\s*miles",
        re.IGNORECASE | re.MULTILINE,
    )

    for parsed in pattern2.finditer(text):
        miles = _normalize_miles(parsed.group("miles"))
        if miles > max_miles:
            continue
        month = int(parsed.group("month"))
        day = int(parsed.group("day"))
        date_iso = f"{current_year:04d}-{month:02d}-{day:02d}"
        matches.append({
            "route": route,
            "date": date_iso,
            "date_label": f"{month}/{day}",
            "miles": miles,
            "taxes": "",
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "source": "parsed_date_strip",
        })

    if matches:
        return matches

    # Pattern 3: Multi-line cabin entries — "Economy: 39.8k miles + $5.60"
    # or "Business: 250k miles + $21.50 (mixed cabin)"
    pattern3 = re.compile(
        r"(?P<cabin_name>Economy|Premium\s*Economy|Business|First|Polaris)"
        r"[^:]*:\s*(?P<miles>[\d,.]+)k?\s*miles"
        r"(?:\s*\+\s*\$(?P<taxes>\d+(?:\.\d{1,2})?))?",
        re.IGNORECASE,
    )

    for parsed in pattern3.finditer(text):
        miles = _normalize_miles(parsed.group("miles"))
        if miles > max_miles:
            continue
        detected_cabin = parsed.group("cabin_name").strip().lower()
        if "polaris" in detected_cabin:
            detected_cabin = "business"
        elif "premium" in detected_cabin:
            detected_cabin = "premium_economy"
        taxes = parsed.group("taxes") or ""
        matches.append({
            "route": route,
            "date": "unknown",
            "date_label": "",
            "miles": miles,
            "taxes": taxes,
            "travelers": travelers,
            "cabin": detected_cabin,
            "mixed_cabin": "mixed" in text[max(0, parsed.start() - 20):parsed.end() + 30].lower(),
            "source": "parsed_cabin_line",
        })

    if matches:
        return matches

    # Pattern 3b: Money+Miles format — "$320 + 15k miles" or "$1,760 + 192k miles"
    # United shows this in Money+Miles pricing mode. Cabin may be on same line or nearby.
    # Also matches "Basic Economy: $250 + 9k miles" or "$984 + 96k miles (Economy)"
    pattern3b = re.compile(
        r"(?:(?P<cabin_prefix>Basic\s*Economy|Economy|Premium\s*Economy|Business|First|Polaris)"
        r"[^:]*:\s*)?"
        r"\$[\d,]+(?:\.\d{1,2})?\s*\+\s*(?P<miles>[\d,.]+)k?\s*miles",
        re.IGNORECASE,
    )

    for parsed in pattern3b.finditer(text):
        miles = _normalize_miles(parsed.group("miles"))
        if miles > max_miles:
            continue
        detected_cabin = cabin
        prefix = (parsed.group("cabin_prefix") or "").strip().lower()
        if prefix:
            if "polaris" in prefix:
                detected_cabin = "business"
            elif "premium" in prefix:
                detected_cabin = "premium_economy"
            elif "basic" in prefix:
                detected_cabin = "economy"
            elif "business" in prefix:
                detected_cabin = "business"
            elif "first" in prefix:
                detected_cabin = "first"
            else:
                detected_cabin = prefix
        matches.append({
            "route": route,
            "date": "unknown",
            "date_label": "",
            "miles": miles,
            "taxes": "",
            "travelers": travelers,
            "cabin": detected_cabin,
            "mixed_cabin": False,
            "source": "parsed_money_plus_miles",
        })

    if matches:
        return matches

    # Pattern 4: Summary lines — "Cheapest economy: 39.8k miles on Feb 22"
    pattern4 = re.compile(
        r"(?:cheapest|best|lowest)\s+(?P<cabin_name>[\w\s]*?):\s*"
        r"(?:\$[\d,]+(?:\.\d{1,2})?\s*\+\s*)?"
        r"(?P<miles>[\d,.]+)k?\s*miles"
        r"(?:\s+on\s+(?P<date_text>[A-Za-z]+\s+\d{1,2}))?",
        re.IGNORECASE,
    )

    for parsed in pattern4.finditer(text):
        miles = _normalize_miles(parsed.group("miles"))
        if miles > max_miles:
            continue
        detected_cabin = parsed.group("cabin_name").strip().lower()
        date_text = parsed.group("date_text") or ""
        matches.append({
            "route": route,
            "date": date_text or "unknown",
            "date_label": date_text,
            "miles": miles,
            "taxes": "",
            "travelers": travelers,
            "cabin": detected_cabin,
            "mixed_cabin": False,
            "source": "parsed_summary_line",
        })

    if matches:
        return matches

    # Last resort: standalone miles values
    for parsed in re.finditer(r"(?P<miles>\d{2,3}(?:,\d{3})?)\s*miles", text, re.IGNORECASE):
        miles = int(parsed.group("miles").replace(",", ""))
        if miles > max_miles:
            continue
        matches.append({
            "route": route,
            "date": "unknown",
            "date_label": "",
            "miles": miles,
            "taxes": "",
            "travelers": travelers,
            "cabin": cabin,
            "mixed_cabin": False,
            "source": "parsed_miles_only",
        })

    return matches
