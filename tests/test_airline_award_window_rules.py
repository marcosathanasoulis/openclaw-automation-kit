from __future__ import annotations

from datetime import date

from library.ana_award import runner as ana_runner
from library.singapore_award import runner as singapore_runner


def test_singapore_filters_scraped_results_to_requested_window() -> None:
    start = date(2026, 3, 8)
    end = date(2026, 3, 10)
    raw_results = [
        {"date": "Mon 09 Mar", "miles": 262000, "raw": "262,000"},
        {"date": "Mon 16 Mar", "miles": 308000, "raw": "308,000"},
        {"date": "Tue 17 Mar", "miles": 308000, "raw": "308,000"},
    ]

    filtered = singapore_runner._filter_results_to_window(raw_results, start, end)

    assert [item["normalized_date"] for item in filtered] == ["2026-03-09"]
    assert filtered[0]["miles"] == 262000


def test_singapore_normalizes_iso_dates_without_rewriting_year() -> None:
    normalized = singapore_runner._normalize_scraped_date("2026-04-07", date(2026, 3, 8))

    assert normalized == date(2026, 4, 7)


def test_ana_reports_96_hour_booking_rule_before_live_run(monkeypatch) -> None:
    monkeypatch.setattr(ana_runner, "browser_agent_enabled", lambda: True)
    monkeypatch.setattr(ana_runner, "date", type("FrozenDate", (), {
        "today": staticmethod(lambda: date(2026, 3, 8)),
    }))

    result = ana_runner.run({}, {
        "from": "SFO",
        "to": ["HND"],
        "days_ahead": 2,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert result["real_data"] is False
    assert result["matches"] == []
    assert "96 hours" in result["summary"]
