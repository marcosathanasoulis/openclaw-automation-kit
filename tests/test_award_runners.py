from pathlib import Path

from openclaw_automation.engine import AutomationEngine
from openclaw_automation.nl import parse_query_to_run


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
    result = engine.run(root / "examples" / "singapore_award", _inputs())
    assert result["ok"] is True
    assert result["script_id"] == "singapore.award_search"
    assert result["result"]["matches"]


def test_ana_runner_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(root / "examples" / "ana_award", _inputs())
    assert result["ok"] is True
    assert result["script_id"] == "ana.award_search"
    assert result["result"]["matches"]


def test_plain_english_query_parsing() -> None:
    parsed = parse_query_to_run(
        "Search ANA award travel economy from SFO to HND for 2 travelers in next 30 days under 120k miles"
    )
    assert parsed.script_dir == "examples/ana_award"
    assert parsed.inputs["cabin"] == "economy"
    assert parsed.inputs["travelers"] == 2

