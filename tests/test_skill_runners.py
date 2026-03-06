"""Tests for skill-level runners (the glue between OpenClaw skills and library runners)."""
from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_award_search_skill_manifest_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    manifest = engine.validate_script(root / "skills" / "openclaw-award-search")
    assert manifest["id"] == "skill.award_search"
    assert manifest["execution_mode"] == "exclusive"


def test_web_automation_skill_manifest_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    manifest = engine.validate_script(root / "skills" / "openclaw-web-automation-basic")
    assert manifest["id"] == "skill.web_automation_basic"
    assert manifest["execution_mode"] == "stateless"


def test_award_search_skill_runner_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "skills" / "openclaw-award-search",
        {"query": "search United SFO to NRT business 2 people max 100k"},
    )
    assert result["ok"] is True
    # The skill runner delegates to the United library runner
    inner = result["result"]
    assert inner["ok"] is True
    assert inner["script_id"] == "united.award_search"


def test_web_automation_skill_runner_with_yahoo() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "skills" / "openclaw-web-automation-basic",
        {"query": "check https://www.yahoo.com for the word news"},
    )
    assert result["ok"] is True
    inner = result["result"]
    assert inner["ok"] is True
    assert inner["result"]["keyword_count"] > 0
