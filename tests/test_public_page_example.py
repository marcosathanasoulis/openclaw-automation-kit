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
    assert parsed.inputs["task"] == "keyword_count"


def test_plain_english_url_maps_with_quoted_keyword() -> None:
    parsed = parse_query_to_run('Load https://www.wikipedia.org and check if "encyclopedia" appears on it')
    assert parsed.script_dir == "examples/public_page_check"
    assert parsed.inputs["url"] == "https://www.wikipedia.org"
    assert parsed.inputs["keyword"] == "encyclopedia"
    assert parsed.inputs["task"] == "keyword_count"


def test_headline_query_maps_to_headlines_task() -> None:
    parsed = parse_query_to_run("Check yahoo.com and tell me the top headlines")
    assert parsed.script_dir == "examples/public_page_check"
    assert parsed.inputs["task"] == "headlines"


def test_fallback_without_airline_uses_public_page_check() -> None:
    parsed = parse_query_to_run("Look at yahoo.com home page and tell me what it says about news")
    assert parsed.script_dir == "examples/public_page_check"


def test_weather_query_maps_to_weather_script() -> None:
    parsed = parse_query_to_run("Check weather in New York in celsius")
    assert parsed.script_dir == "examples/weather_check"
    assert parsed.inputs["location"] == "New York"
    assert parsed.inputs["temperature_unit"] == "celsius"


def test_weather_manifest_validates() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    manifest = engine.validate_script(root / "examples" / "weather_check")
    assert manifest["id"] == "examples.weather_check"
