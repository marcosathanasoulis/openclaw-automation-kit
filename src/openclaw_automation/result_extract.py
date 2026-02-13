from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List


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

    current_year = datetime.now().year
    matches: List[Dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<label>[A-Za-z]{3}\s+\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})[:\-\s]+"
        r"(?P<miles>\d+(?:\.\d+)?)k\s*miles?\s*\+\s*\$(?P<taxes>\d+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    for m in pattern.finditer(text):
        label = m.group("label").strip()
        miles = int(float(m.group("miles")) * 1000)
        if miles > max_miles:
            continue
        taxes = m.group("taxes")

        date_iso = ""
        md = re.search(r"(\d{1,2})/(\d{1,2})", label)
        if md:
            month = int(md.group(1))
            day = int(md.group(2))
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

    return matches

