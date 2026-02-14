from __future__ import annotations

from openclaw_automation.result_extract import extract_award_matches_from_text


def test_extract_award_matches_from_text_filters_by_max_miles() -> None:
    text = (
        "Fri 2/27: 200k miles + $5.60\n"
        "Mon 3/2: 80k miles + $5.60\n"
        "Tue 3/3: 80k miles + $29.50\n"
    )
    matches = extract_award_matches_from_text(
        text,
        route="SFO-CDG",
        cabin="business",
        travelers=2,
        max_miles=120000,
    )
    assert len(matches) == 2
    assert matches[0]["miles"] == 80000
    assert matches[0]["route"] == "SFO-CDG"


def test_extract_award_matches_from_match_line_format() -> None:
    text = (
        "MATCH|2026-03-02|80000|29.50|1 stop|Lufthansa|overnight\n"
        "MATCH|2026-03-03|130000|5.60|nonstop|United|over budget\n"
    )
    matches = extract_award_matches_from_text(
        text,
        route="SFO-AMS",
        cabin="business",
        travelers=2,
        max_miles=120000,
    )
    assert len(matches) == 1
    assert matches[0]["date"] == "2026-03-02"
    assert matches[0]["miles"] == 80000
    assert matches[0]["source"] == "match_line"
