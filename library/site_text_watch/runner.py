from __future__ import annotations

import re
import urllib.request
from typing import Any, Dict, List


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (OpenClawAutomationKit/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        page_html = resp.read().decode("utf-8", errors="ignore")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page_html)).strip()


def _contains(haystack: str, needle: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return needle in haystack
    return needle.lower() in haystack.lower()


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    url = str(inputs["url"])
    must_include = [str(x) for x in inputs.get("must_include", [])]
    must_not_include = [str(x) for x in inputs.get("must_not_include", [])]
    case_sensitive = bool(inputs.get("case_sensitive", False))

    try:
        page_text = _fetch_text(url)
        present_required: List[str] = [x for x in must_include if _contains(page_text, x, case_sensitive)]
        missing_required: List[str] = [x for x in must_include if x not in present_required]
        forbidden_found: List[str] = [x for x in must_not_include if _contains(page_text, x, case_sensitive)]
        all_required_present = len(missing_required) == 0

        summary = (
            f"Checked {url}. "
            f"Required present: {len(present_required)}/{len(must_include)}. "
            f"Forbidden hits: {len(forbidden_found)}."
        )
        return {
            "url": url,
            "all_required_present": all_required_present,
            "present_required": present_required,
            "missing_required": missing_required,
            "forbidden_found": forbidden_found,
            "summary": summary,
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "all_required_present": False,
            "present_required": [],
            "missing_required": must_include,
            "forbidden_found": [],
            "summary": f"Failed to fetch {url}",
            "errors": [str(exc)],
        }
