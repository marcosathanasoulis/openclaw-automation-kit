from __future__ import annotations

import shutil
from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_placeholder_mode_is_promoted_to_top_level() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "library" / "united_award",
        {
            "from": "SFO",
            "to": ["AMS"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "economy",
        },
    )
    assert result["ok"] is True
    assert result["mode"] == "placeholder"
    assert result["real_data"] is False
    assert result["warnings"]


def test_output_schema_validation_failure_returns_structured_error(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    script_src = root / "examples" / "public_page_check"
    script_dst = tmp_path / "broken_script"
    shutil.copytree(script_src, script_dst)
    (script_dst / "runner.py").write_text(
        "def run(context, inputs):\n"
        "    return {'summary': 'bad output only'}\n",
        encoding="utf-8",
    )

    engine = AutomationEngine(root)
    result = engine.run(script_dst, {"url": "https://example.com", "keyword": "test"})
    assert result["ok"] is False
    assert result["script_id"] == "web.public_page_check"
    assert "output schema validation failed" in result["error"]
