from pathlib import Path
import sys

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


def test_united_runner_fallback_starts_on_award_results_url(monkeypatch) -> None:
    captured = {}

    def fake_run_browser_agent_goal(**kwargs):
        captured.update(kwargs)
        return {"ok": False, "error": "forced adapter failure", "result": None}

    monkeypatch.setattr(united_runner, "_run_homepage_award_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(united_runner, "_run_direct_award_search", lambda *_args, **_kwargs: None)
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
        "SFO", "BKK", depart_date, "business", 2, award=True,
    )

    assert captured["url"] == expected_url
    assert result["mode"] == "placeholder"


def test_united_runner_prefers_homepage_live_path(monkeypatch) -> None:
    sentinel = {
        "mode": "live",
        "real_data": True,
        "matches": [{"route": "SFO-BKK", "miles": 250000, "cabin": "business"}],
        "booking_url": "https://example.com",
        "summary": "homepage path",
        "raw_observations": [],
        "errors": [],
    }

    monkeypatch.setattr(united_runner, "_run_homepage_award_search", lambda *_args, **_kwargs: sentinel)
    monkeypatch.setattr(
        united_runner,
        "_run_direct_award_search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct path should not run")),
    )

    result = united_runner.run({}, {
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 30,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert result is sentinel


def test_united_award_url_uses_real_award_params() -> None:
    depart_date = united_runner.date(2026, 4, 6)

    url = united_runner._booking_url(
        "SFO", "BKK", depart_date, "business", 2, award=True,
    )

    assert "at=1" in url
    assert "tqp=A" in url
    assert "act=2" in url
    assert "px=2%2C0%2C0%2C0%2C0%2C0%2C0%2C0" in url
    assert "sc=6" in url


def test_united_result_text_parser_prefers_business_and_marks_mixed() -> None:
    text = """
    67.8k
    miles
    +
    $24.80
    United Economy (YN)
    Select fare for Economy
    200k
    miles
    +
    $24.80
    United Premium Plus (ON)
    Select fare for Premium Economy
    250k
    miles
    +
    $36.30
    United Polaris business (JN)
    Select fare for Business (lowest)
    Flight Information

    55k
    miles
    +
    $23.20
    Saver Award
    Select fare for Economy
    200k
    miles
    +
    $23.20
    Mixed cabin
    Select fare for Premium Economy
    250k
    miles
    +
    $23.20
    Mixed cabin
    Select fare for Business (lowest)
    Flight Information
    """

    matches = united_runner._extract_united_matches_from_text(
        text,
        route="SFO-BKK",
        depart_date=united_runner.date(2026, 4, 7),
        travelers=2,
        cabin="business",
        max_miles=500000,
    )

    assert len(matches) == 2
    assert matches[0]["miles"] == 250000
    assert matches[0]["taxes"] == "36.30"
    assert matches[0]["mixed_cabin"] is False
    assert matches[0]["carrier"] == "United"
    assert matches[1]["miles"] == 250000
    assert matches[1]["taxes"] == "23.20"
    assert matches[1]["mixed_cabin"] is True


def test_united_calendar_text_parser_reads_7day_business_strip() -> None:
    text = """
    Choose Saturday, April 4, 2026 with fares starting at
    Sat 4/4
    250k miles
    miles
    +
    plus
    $23.20
    Choose Sunday, April 5, 2026 with fares starting at
    Sun 4/5
    250k miles
    miles
    +
    plus
    $36.30
    Now Showing Monday, April 6, 2026 with fares starting at
    Mon 4/6
    240k miles
    miles
    +
    plus
    $28.00
    """

    matches = united_runner._extract_united_calendar_matches_from_text(
        text,
        route="SFO-BKK",
        travelers=2,
        cabin="business",
        max_miles=500000,
    )

    assert [match["date"] for match in matches] == ["2026-04-04", "2026-04-05", "2026-04-06"]
    assert [match["miles"] for match in matches] == [250000, 250000, 240000]
    assert all(match["cabin"] == "business" for match in matches)
    assert all(match["mixed_cabin"] is False for match in matches)
    assert all(match["source"] == "united_7day_calendar" for match in matches)


def test_united_match_filter_drops_mixed_business_rows() -> None:
    filtered = united_runner._filter_united_matches(
        [
            {
                "date": "2026-04-07",
                "miles": 250000,
                "taxes": "36.30",
                "cabin": "business",
                "mixed_cabin": False,
                "source": "detail",
            },
            {
                "date": "2026-04-07",
                "miles": 250000,
                "taxes": "23.20",
                "cabin": "business",
                "mixed_cabin": True,
                "source": "detail",
            },
        ],
        cabin="business",
        allow_mixed=False,
    )

    assert filtered == [
        {
            "date": "2026-04-07",
            "miles": 250000,
            "taxes": "36.30",
            "cabin": "business",
            "mixed_cabin": False,
            "source": "detail",
        }
    ]


def test_united_wait_for_award_results_ignores_skeleton_shell(monkeypatch) -> None:
    class DummyLocator:
        def inner_text(self, timeout: int = 0) -> str:
            return "Flight Search Results Loading results..."

    class DummyPage:
        def wait_for_load_state(self, *_args, **_kwargs) -> None:
            return None

        def locator(self, _selector: str) -> DummyLocator:
            return DummyLocator()

    states = iter(
        [
            {
                "body_len": 1609,
                "miles_mentions": 5,
                "flight_cards": 0,
                "skeletons": 440,
                "no_results": False,
                "invalid_credentials": False,
            },
            {
                "body_len": 1609,
                "miles_mentions": 5,
                "flight_cards": 0,
                "skeletons": 440,
                "no_results": False,
                "invalid_credentials": False,
            },
            {
                "body_len": 23084,
                "miles_mentions": 112,
                "flight_cards": 4,
                "skeletons": 0,
                "no_results": False,
                "invalid_credentials": False,
            },
        ]
    )
    calls = {"count": 0}

    def fake_page_state(_page: DummyPage) -> dict:
        calls["count"] += 1
        return next(states)

    class Clock:
        def __init__(self) -> None:
            self.value = 0

        def time(self) -> int:
            self.value += 1
            return self.value

        def sleep(self, _seconds: int) -> None:
            return None

    clock = Clock()

    monkeypatch.setattr(united_runner, "_dismiss_united_overlays", lambda _page: None)
    monkeypatch.setattr(united_runner, "_page_is_live", lambda _page: True)
    monkeypatch.setattr(united_runner, "_page_state", fake_page_state)
    monkeypatch.setattr(united_runner.time, "time", clock.time)
    monkeypatch.setattr(united_runner.time, "sleep", clock.sleep)

    united_runner._wait_for_award_results(DummyPage(), timeout_s=10)

    assert calls["count"] == 3


def test_united_wait_for_award_results_accepts_loaded_calendar(monkeypatch) -> None:
    class DummyLocator:
        def inner_text(self, timeout: int = 0) -> str:
            return """
            Choose Saturday, April 4, 2026 with fares starting at
            Sat 4/4
            250k miles
            +
            plus
            $23.20
            Choose Sunday, April 5, 2026 with fares starting at
            Sun 4/5
            250k miles
            +
            plus
            $36.30
            Choose Monday, April 6, 2026 with fares starting at
            Mon 4/6
            240k miles
            +
            plus
            $28.00
            Choose Tuesday, April 7, 2026 with fares starting at
            Tue 4/7
            240k miles
            +
            plus
            $28.00
            Choose Wednesday, April 8, 2026 with fares starting at
            Wed 4/8
            240k miles
            +
            plus
            $28.00
            """

    class DummyPage:
        def wait_for_load_state(self, *_args, **_kwargs) -> None:
            return None

        def locator(self, _selector: str) -> DummyLocator:
            return DummyLocator()

    calls = {"count": 0}

    def fake_page_state(_page: DummyPage) -> dict:
        calls["count"] += 1
        return {
            "body_len": 2200,
            "miles_mentions": 18,
            "flight_cards": 0,
            "skeletons": 0,
            "no_results": False,
            "invalid_credentials": False,
        }

    monkeypatch.setattr(united_runner, "_dismiss_united_overlays", lambda _page: None)
    monkeypatch.setattr(united_runner, "_page_is_live", lambda _page: True)
    monkeypatch.setattr(united_runner, "_page_state", fake_page_state)
    monkeypatch.setattr(united_runner.time, "sleep", lambda _seconds: None)

    united_runner._wait_for_award_results(DummyPage(), timeout_s=5)

    assert calls["count"] == 1


def test_united_browser_helpers_accept_file_path(tmp_path, monkeypatch) -> None:
    helper = tmp_path / "tmp_browser_agent.py"
    helper.write_text(
        "def get_credentials(*_args, **_kwargs):\n"
        "    return ('ka388724', 'secret')\n"
        "\n"
        "def read_sms_code(*_args, **_kwargs):\n"
        "    return '123456'\n"
    )

    monkeypatch.setenv("OPENCLAW_BROWSER_AGENT_PATH", str(helper))
    monkeypatch.delenv("OPENCLAW_BROWSER_AGENT_MODULE", raising=False)
    sys.modules.pop("tmp_browser_agent", None)

    get_credentials, read_sms_code = united_runner._load_browser_helpers()

    assert get_credentials is not None
    assert read_sms_code is not None
    assert get_credentials("www.united.com") == ("ka388724", "secret")
    assert read_sms_code() == "123456"
