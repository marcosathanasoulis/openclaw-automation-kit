from pathlib import Path

from openclaw_automation.engine import AutomationEngine
from openclaw_automation.nl import parse_query_to_run
from library.united_award import runner as united_runner


def _inputs() -> dict:
    return {
        "from": "SFO",
        "to": ["NRT", "SIN"],
        "days_ahead": 30,
        "max_miles": 120000,
        "travelers": 2,
        "cabin": "economy",
    }


def test_singapore_runner_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(root / "library" / "singapore_award", _inputs())
    assert result["ok"] is True
    assert result["script_id"] == "singapore.award_search"
    assert result["result"]["matches"]


def test_ana_runner_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(root / "library" / "ana_award", _inputs())
    assert result["ok"] is True
    assert result["script_id"] == "ana.award_search"
    assert result["result"]["matches"]


def test_plain_english_query_parsing() -> None:
    parsed = parse_query_to_run(
        "Search ANA award travel economy from SFO to HND for 2 travelers in next 30 days under 120k miles"
    )
    assert parsed.script_dir == "library/ana_award"
    assert parsed.inputs["cabin"] == "economy"
    assert parsed.inputs["travelers"] == 2


def test_united_runner_starts_on_cash_results_url(monkeypatch) -> None:
    captured = {}

    def fake_run_browser_agent_goal(**kwargs):
        captured.update(kwargs)
        return {"ok": False, "error": "forced adapter failure", "result": None}

    monkeypatch.setattr(united_runner, "browser_agent_enabled", lambda: True)
    monkeypatch.setattr(united_runner, "run_browser_agent_goal", fake_run_browser_agent_goal)

    inputs = {
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 30,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    }

    result = united_runner.run({}, inputs)

    depart_date = united_runner.date.today() + united_runner.timedelta(days=30)
    expected_url = united_runner._booking_url(
        "SFO", "BKK", depart_date, "business", 2, award=False,
    )

    assert captured["url"] == expected_url
    assert result["mode"] == "placeholder"
