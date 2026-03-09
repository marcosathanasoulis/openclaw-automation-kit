from library.united_award import runner as united_runner


def test_united_goal_uses_homepage_flow_and_business_filters() -> None:
    goal = united_runner._goal({
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 1,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert "Use the United homepage search form" in goal
    assert "Book with miles" in goal
    assert "select the Business fare view and hide mixed cabin fares" in goal
    assert "7-day strip" in goal


def test_united_runner_browser_agent_fallback_starts_on_homepage(monkeypatch) -> None:
    captured = {}

    def fake_run_browser_agent_goal(**kwargs):
        captured.update(kwargs)
        return {"ok": False, "error": "forced adapter failure", "result": None}

    monkeypatch.setattr(united_runner, "_run_homepage_award_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(united_runner, "browser_agent_enabled", lambda: True)
    monkeypatch.setattr(united_runner, "run_browser_agent_goal", fake_run_browser_agent_goal)

    result = united_runner.run({}, {
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 30,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert captured["url"] == united_runner.UNITED_URL
    assert result["mode"] == "live"
    assert result["real_data"] is False
    assert result["matches"] == []
    assert "forced adapter failure" in result["errors"][0]


def test_united_runner_skips_direct_path_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENCLAW_UNITED_ENABLE_DIRECT_PATH", raising=False)
    monkeypatch.setattr(united_runner, "_run_homepage_award_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        united_runner,
        "_run_direct_award_search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("direct path should be opt-in only")),
    )
    monkeypatch.setattr(united_runner, "browser_agent_enabled", lambda: False)

    result = united_runner.run({}, {
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 30,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert result["mode"] == "placeholder"
    assert any("disabled by default" in note for note in result["raw_observations"])


def test_united_close_sign_in_modal_reports_success(monkeypatch) -> None:
    visible = {"count": 2}
    pressed = []
    clicked = []

    monkeypatch.setattr(united_runner, "_try_click_any", lambda *_args, **_kwargs: clicked.append(True) or True)
    monkeypatch.setattr(united_runner, "_dismiss_united_overlays", lambda _page: None)
    monkeypatch.setattr(united_runner.time, "sleep", lambda _seconds: None)

    def fake_visible(_page):
        visible["count"] -= 1
        return visible["count"] >= 0

    monkeypatch.setattr(united_runner, "_is_sign_in_visible", fake_visible)

    class DummyKeyboard:
        def press(self, key: str) -> None:
            pressed.append(key)

    class DummyPage:
        keyboard = DummyKeyboard()

    observations: list[str] = []
    ok = united_runner._close_united_sign_in_modal(DummyPage(), observations)

    assert ok is True
    assert clicked
    assert "Escape" in pressed
    assert any("dismissed sign-in modal" in note for note in observations)


def test_united_runner_allows_direct_path_when_enabled(monkeypatch) -> None:
    sentinel = {
        "mode": "live",
        "real_data": True,
        "matches": [{"route": "SFO-BKK", "miles": 250000, "cabin": "business"}],
        "booking_url": "https://example.com/direct",
        "summary": "direct path",
        "raw_observations": [],
        "errors": [],
    }

    monkeypatch.setenv("OPENCLAW_UNITED_ENABLE_DIRECT_PATH", "1")
    monkeypatch.setattr(united_runner, "_run_homepage_award_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(united_runner, "browser_agent_enabled", lambda: False)
    monkeypatch.setattr(united_runner, "_run_direct_award_search", lambda *_args, **_kwargs: sentinel)

    result = united_runner.run({}, {
        "from": "SFO",
        "to": ["BKK"],
        "days_ahead": 30,
        "max_miles": 500000,
        "travelers": 2,
        "cabin": "business",
    })

    assert result is sentinel


def test_united_fill_selector_uses_visible_match_after_hidden_first() -> None:
    class DummyField:
        def __init__(self, visible: bool) -> None:
            self.visible = visible
            self.typed: list[str] = []

        def is_visible(self) -> bool:
            return self.visible

        def click(self, timeout: int = 0) -> None:
            return None

        def fill(self, _value: str) -> None:
            return None

        def type(self, value: str, delay: int = 0) -> None:
            self.typed.append(value)

        def evaluate(self, _script: str, _value: str | None = None) -> bool:
            return True

    class DummyLocatorGroup:
        def __init__(self, fields: list[DummyField]) -> None:
            self.fields = fields

        def count(self) -> int:
            return len(self.fields)

        def nth(self, idx: int) -> DummyField:
            return self.fields[idx]

    class DummyPage:
        def __init__(self, fields: list[DummyField]) -> None:
            self.fields = fields

        def locator(self, _selector: str) -> DummyLocatorGroup:
            return DummyLocatorGroup(self.fields)

    hidden = DummyField(False)
    visible = DummyField(True)

    ok = united_runner._fill_selector(DummyPage([hidden, visible]), ["#bookFlightDestinationInput"], "BKK")

    assert ok is True
    assert hidden.typed == []
    assert visible.typed == ["BKK"]


def test_united_wait_for_active_page_in_browser_prefers_current_live_page(monkeypatch) -> None:
    class DummyPage:
        url = "https://www.united.com/en/us/fsr/choose-flights?f=SFO&t=BKK"

        def is_closed(self) -> bool:
            return False

    current_context = object()
    current_page = DummyPage()

    monkeypatch.setattr(
        united_runner,
        "_select_cdp_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not scan other tabs")),
    )

    context, page = united_runner._wait_for_active_united_page_in_browser(
        browser=object(),
        current_context=current_context,
        current_page=current_page,
        timeout_s=1,
    )

    assert context is current_context
    assert page is current_page


def test_united_credentials_skip_generic_keychain_fallback_when_username_fixed(monkeypatch) -> None:
    calls = []

    def fake_get_credentials(domain: str, account: str | None = None):
        calls.append((domain, account))
        if account == "ka388724":
            return ("ka388724", "pw123")
        if account is None:
            return ("WRONG", "badpw")
        return None

    monkeypatch.setattr(united_runner, "_load_browser_helpers", lambda: (fake_get_credentials, None))
    monkeypatch.delenv("OPENCLAW_SECRET_OPENCLAW_UNITED_PASSWORD", raising=False)

    username, password = united_runner._resolve_united_credentials({})

    assert username == "ka388724"
    assert password == "pw123"
    assert calls == [("www.united.com", "ka388724")]


def test_united_finalize_prefers_calendar_after_mixed_hidden(monkeypatch) -> None:
    class DummyPage:
        url = "https://www.united.com/en/us/fsr/choose-flights?f=SFO&t=BKK"

    calendar_matches = [
        {
            "route": "SFO-BKK",
            "date": f"2026-03-{day:02d}",
            "date_label": f"Mar {day:02d}",
            "miles": 100000 + idx * 1000,
            "taxes": "23.20",
            "travelers": 2,
            "cabin": "business",
            "mixed_cabin": False,
            "source": "united_7day_calendar",
            "notes": "7-day calendar starting fare",
        }
        for idx, day in enumerate(range(9, 16))
    ]
    detail_matches = [
        {
            "route": "SFO-BKK",
            "date": "2026-03-09",
            "date_label": "Mar 09",
            "miles": 250000,
            "taxes": "23.20",
            "travelers": 2,
            "cabin": "business",
            "mixed_cabin": False,
            "source": "united_result_text",
        }
    ]

    monkeypatch.setattr(united_runner, "_page_is_live", lambda _page: True)
    monkeypatch.setattr(
        united_runner,
        "_page_state",
        lambda _page: {"flight_cards": 0, "miles_mentions": 80, "skeletons": 0, "no_results": False, "invalid_credentials": False},
    )
    monkeypatch.setattr(united_runner, "_configure_united_results_view", lambda *_args, **_kwargs: {"sorted": True, "mixed_hidden": True})
    monkeypatch.setattr(united_runner, "_wait_for_award_results", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(united_runner, "_collect_result_text", lambda _page: "stub")
    monkeypatch.setattr(united_runner, "_extract_united_calendar_matches_from_text", lambda *_args, **_kwargs: calendar_matches)
    monkeypatch.setattr(united_runner, "_extract_united_matches_from_text", lambda *_args, **_kwargs: detail_matches)
    monkeypatch.setattr(united_runner, "_filter_united_matches", lambda matches, **_kwargs: matches)

    result = united_runner._finalize_united_result_page(
        DummyPage(),
        [],
        origin="SFO",
        dest="BKK",
        depart_date=united_runner.date(2026, 3, 9),
        travelers=2,
        cabin="business",
        max_miles=500000,
        booking_url="https://example.com",
        context_label="homepage search",
    )

    assert result["real_data"] is True
    assert result["matches"] == calendar_matches
    assert result["calendar_matches"] == calendar_matches
    assert result["detail_matches"] == detail_matches
