from __future__ import annotations

from openclaw_automation.nl import parse_query_to_run


def test_google_news_headlines_route() -> None:
    parsed = parse_query_to_run("Fetch the latest headlines from Google News")
    assert parsed.script_dir == "library/site_headlines"
    assert parsed.inputs["url"] == "https://news.google.com"
    assert parsed.inputs["max_items"] == 12


def test_restaurant_query_routes_to_web_search_brief() -> None:
    parsed = parse_query_to_run("Find the best French restaurant in Marin County, California")
    assert parsed.script_dir == "library/web_search_brief"
    assert parsed.inputs["kind"] == "restaurant"
    assert "Marin County" in parsed.inputs["query"] or "marin county" in parsed.inputs["query"].lower()


def test_hotel_query_routes_to_web_search_brief() -> None:
    parsed = parse_query_to_run(
        "Find the best hotel prices for March 12-15 in Manhattan for a one-bedroom suite"
    )
    assert parsed.script_dir == "library/web_search_brief"
    assert parsed.inputs["kind"] == "hotel"
    assert "Manhattan" in parsed.inputs["query"] or "manhattan" in parsed.inputs["query"].lower()


def test_explicit_url_still_uses_public_page_check() -> None:
    parsed = parse_query_to_run("Check https://example.com and summarize headlines")
    assert parsed.script_dir == "examples/public_page_check"
    assert parsed.inputs["url"] == "https://example.com"
