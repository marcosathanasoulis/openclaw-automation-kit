from pathlib import Path

from openclaw_automation.engine import AutomationEngine
from openclaw_automation.nl import parse_query_to_run


def test_public_page_manifest_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    manifest = engine.validate_script(root / "examples" / "public_page_check")
    assert manifest["id"] == "web.public_page_check"


def test_plain_english_url_maps_to_public_page_script() -> None:
    parsed = parse_query_to_run("Open https://www.yahoo.com and count mentions of news")
    assert parsed.script_dir == "examples/public_page_check"
    assert parsed.inputs["url"] == "https://www.yahoo.com"
    assert parsed.inputs["keyword"] == "news"


def test_plain_english_url_maps_with_quoted_keyword() -> None:
    parsed = parse_query_to_run('Load https://crediblemind.com and check if "mental health" appears on it')
    assert parsed.script_dir == "examples/public_page_check"
    assert parsed.inputs["url"] == "https://crediblemind.com"
    assert parsed.inputs["keyword"] == "mental health"


def test_fallback_without_airline_uses_public_page_check() -> None:
    parsed = parse_query_to_run("Look at yahoo.com home page and tell me what it says about news")
    assert parsed.script_dir == "examples/public_page_check"
