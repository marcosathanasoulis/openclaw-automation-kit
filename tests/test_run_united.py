from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_united_runner_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "examples" / "united_award",
        {
            "from": "SFO",
            "to": ["AMS", "LIS", "FCO"],
            "days_ahead": 30,
            "max_miles": 120000,
            "travelers": 2,
        },
    )

    assert result["ok"] is True
    assert result["script_id"] == "united.award_search"
    assert result["result"]["matches"]
