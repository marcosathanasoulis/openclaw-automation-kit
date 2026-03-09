from __future__ import annotations

from datetime import date

from library.singapore_award import runner as singapore_runner


class _FakeLocator:
    def __init__(self, visible: bool) -> None:
        self._visible = visible
        self.first = self

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        if not self._visible:
            raise RuntimeError("not visible")


class _FakePage:
    def __init__(self, visible_selectors: set[str]) -> None:
        self.visible_selectors = visible_selectors

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(selector in self.visible_selectors)


def test_wait_for_redeem_widget_accepts_live_field_selectors() -> None:
    page = _FakePage(
        {
            "input[name='flightOrigin']",
            "input[name='redeemFlightDestination']",
            "input[name='departDate']",
            "input[name='flightClass']",
            "input[name='flightPassengers']",
        }
    )

    assert singapore_runner._wait_for_redeem_widget(page, timeout=1) is True


def test_wait_for_redeem_widget_fails_closed_when_field_missing() -> None:
    page = _FakePage(
        {
            "input[name='flightOrigin']",
            "input[name='redeemFlightDestination']",
            "input[name='departDate']",
            "input[name='flightClass']",
        }
    )

    assert singapore_runner._wait_for_redeem_widget(page, timeout=1) is False


def test_login_goal_requires_explicit_submit_after_password() -> None:
    goal = singapore_runner._login_goal()

    assert "EXPLICITLY click the visible Log in / Sign in / Submit button." in goal
    assert "Do not stop after typing the password." in goal
    assert "If the current tab becomes about:blank" in goal


def test_search_anchor_days_centers_longer_windows() -> None:
    assert singapore_runner._search_anchor_days(2) == 2
    assert singapore_runner._search_anchor_days(7) == 7
    assert singapore_runner._search_anchor_days(30) == 14


def test_results_page_matches_search_context() -> None:
    page_text = """
    SFO-BKK
    2 Adults
    One way
    07 APR (TUE)
    SHOW FLIGHTS FOR
    """

    assert singapore_runner._results_page_matches_search(
        page_text,
        "SFO",
        "BKK",
        2,
        date(2026, 4, 7),
    ) is True


def test_results_page_match_rejects_wrong_search_context() -> None:
    page_text = """
    SFO-SIN
    1 Adult
    Round trip
    08 APR (WED)
    SHOW FLIGHTS FOR
    """

    assert singapore_runner._results_page_matches_search(
        page_text,
        "SFO",
        "BKK",
        2,
        date(2026, 4, 7),
    ) is False
