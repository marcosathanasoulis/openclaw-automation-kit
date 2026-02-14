from __future__ import annotations

import html
import re
import urllib.request
from typing import Any, Dict, List, Tuple


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (OpenClawAutomationKit/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_title_and_headlines(page_html: str, max_items: int) -> Tuple[str, List[str]]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL)
    title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else "Untitled"

    headlines: List[str] = []
    for level in ("h1", "h2", "h3"):
        pattern = rf"<{level}[^>]*>(.*?)</{level}>"
        for match in re.finditer(pattern, page_html, flags=re.IGNORECASE | re.DOTALL):
            raw = re.sub(r"<[^>]+>", " ", match.group(1))
            text = html.unescape(re.sub(r"\s+", " ", raw)).strip()
            if len(text) < 4:
                continue
            if text in headlines:
                continue
            headlines.append(text)
            if len(headlines) >= max_items:
                return title, headlines
    return title, headlines


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    url = str(inputs["url"])
    max_items = int(inputs.get("max_items", 8))

    try:
        page_html = _fetch_html(url)
        title, headlines = _extract_title_and_headlines(page_html, max_items=max_items)
        summary = (
            f"Fetched {url}. "
            + (f"Top headlines: {' | '.join(headlines[:5])}" if headlines else f"No H1/H2/H3 headings found. Title: {title}")
        )
        return {
            "url": url,
            "title": title,
            "headlines": headlines,
            "summary": summary,
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "title": "Unavailable",
            "headlines": [],
            "summary": f"Failed to fetch {url}",
            "errors": [str(exc)],
        }
