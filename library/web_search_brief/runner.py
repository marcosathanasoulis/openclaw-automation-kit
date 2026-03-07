from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List

SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"

_TITLE_RE = re.compile(
    r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    flags=re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>',
    flags=re.IGNORECASE | re.DOTALL,
)
_PRICE_RE = re.compile(
    r"(?:US\$|\$)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)",
    flags=re.IGNORECASE,
)


def _search_url(query: str) -> str:
    encoded = urllib.parse.urlencode({"q": query, "kl": "us-en"})
    return f"{SEARCH_ENDPOINT}?{encoded}"


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (OpenClawAutomationKit/1.0)", "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _strip_tags(fragment: str) -> str:
    raw = re.sub(r"<[^>]+>", " ", fragment or "")
    return html.unescape(re.sub(r"\s+", " ", raw)).strip()


def _decode_result_url(raw_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    qs = urllib.parse.parse_qs(parsed.query)
    uddg = qs.get("uddg", [])
    if uddg:
        return urllib.parse.unquote(uddg[0])
    return raw_url


def _extract_price_hints(text: str) -> List[float]:
    prices: List[float] = []
    seen = set()
    for match in _PRICE_RE.finditer(text):
        raw = match.group(1)
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        prices.append(value)
    return prices


def _extract_results(page_html: str, max_results: int) -> List[Dict[str, Any]]:
    anchors = list(_TITLE_RE.finditer(page_html))
    results: List[Dict[str, Any]] = []
    for idx, match in enumerate(anchors[: max_results * 2]):
        raw_url = match.group(1)
        title = _strip_tags(match.group(2))
        if not title:
            continue
        start = match.end()
        if idx + 1 < len(anchors):
            end = anchors[idx + 1].start()
        else:
            end = min(len(page_html), start + 4000)
        segment = page_html[start:end]
        snippet_match = _SNIPPET_RE.search(segment)
        snippet = _strip_tags(snippet_match.group(1)) if snippet_match else ""
        result_url = _decode_result_url(html.unescape(raw_url))
        prices = _extract_price_hints(f"{title} {snippet}")
        results.append(
            {
                "rank": len(results) + 1,
                "title": title,
                "url": result_url,
                "snippet": snippet,
                "price_hints": prices,
            }
        )
        if len(results) >= max_results:
            break
    return results


def _best_price_hint(results: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    best = None
    for result in results:
        for value in result.get("price_hints", []):
            if best is None or value < best["value"]:
                best = {
                    "value": value,
                    "title": result["title"],
                    "url": result["url"],
                    "rank": result["rank"],
                }
    return best


def _summary(kind: str, query: str, results: List[Dict[str, Any]], best_price_hint: Dict[str, Any] | None) -> str:
    if not results:
        return f"No search results found for: {query}"
    if kind == "hotel":
        if best_price_hint:
            return (
                f"Found {len(results)} hotel search results. "
                f"Lowest visible price hint is ${best_price_hint['value']:,.2f} "
                f"(rank #{best_price_hint['rank']}: {best_price_hint['title']})."
            )
        return f"Found {len(results)} hotel search results. No explicit price hints were detected in snippets."
    if kind == "restaurant":
        top_titles = " | ".join(r["title"] for r in results[:3])
        return f"Found {len(results)} restaurant search results. Top leads: {top_titles}"
    top_titles = " | ".join(r["title"] for r in results[:3])
    return f"Found {len(results)} web results for '{query}'. Top results: {top_titles}"


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    query = str(inputs["query"]).strip()
    max_results = int(inputs.get("max_results", 8))
    kind = str(inputs.get("kind", "generic")).strip().lower() or "generic"
    if kind not in {"generic", "restaurant", "hotel"}:
        kind = "generic"

    search_url = _search_url(query)
    try:
        page_html = _fetch_html(search_url)
        results = _extract_results(page_html, max_results=max_results)
        best = _best_price_hint(results)
        return {
            "query": query,
            "search_url": search_url,
            "results": results,
            "best_price_hint": best,
            "summary": _summary(kind, query, results, best),
            "errors": [],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "query": query,
            "search_url": search_url,
            "results": [],
            "best_price_hint": None,
            "summary": f"Search failed for: {query}",
            "errors": [str(exc)],
        }
