from __future__ import annotations

import html
import re
from typing import Any, Dict, List
from urllib.request import Request, urlopen


def _fetch_html(url: str) -> str:
    req = Request(
        url=url,
        headers={
            "User-Agent": "OpenClawAutomationKit/0.1 (+https://github.com/marcosathanasoulis/openclaw-automation-kit)"
        },
    )
    with urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _extract_title(page_html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return "Untitled page"
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()


def _visible_text(page_html: str) -> str:
    no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page_html, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_script)
    return html.unescape(re.sub(r"\s+", " ", no_tags)).strip()


def _sentence_highlights(text: str, keyword: str, max_items: int = 3) -> List[str]:
    pieces = re.split(r"(?<=[.!?])\s+", text)
    out: List[str] = []
    key = keyword.lower()
    for piece in pieces:
        if key in piece.lower():
            out.append(piece.strip())
        if len(out) >= max_items:
            break
    return out


def _extract_headlines(page_html: str, max_items: int = 8) -> List[str]:
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
                return headlines
    return headlines


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    url = str(inputs["url"])
    keyword = str(inputs.get("keyword", "mental")).strip() or "mental"
    task = str(inputs.get("task", "keyword_count")).strip().lower() or "keyword_count"

    try:
        page_html = _fetch_html(url)
        title = _extract_title(page_html)
        text = _visible_text(page_html)
        keyword_count = len(re.findall(re.escape(keyword), text, flags=re.IGNORECASE))
        highlights = _sentence_highlights(text, keyword)
        headlines = _extract_headlines(page_html)

        if task == "headlines":
            if headlines:
                summary = f"Fetched {url}. Top headlines: " + " | ".join(headlines[:5])
            else:
                summary = f"Fetched {url}. No clear headline tags found; title is '{title}'."
        elif task == "summary":
            summary = f"Fetched {url}. Title: {title}. Found {len(headlines)} heading(s)."
        else:
            summary = (
                f"Fetched {url}. Title: {title}. "
                f"The word '{keyword}' appears {keyword_count} time(s)."
            )
        return {
            "url": url,
            "title": title,
            "task": task,
            "keyword": keyword,
            "keyword_count": keyword_count,
            "headlines": headlines,
            "highlights": highlights,
            "summary": summary,
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "title": "Unavailable",
            "task": task,
            "keyword": keyword,
            "keyword_count": 0,
            "headlines": [],
            "highlights": [],
            "summary": f"Failed to fetch {url}",
            "errors": [str(exc)],
        }
