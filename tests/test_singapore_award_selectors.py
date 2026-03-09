from __future__ import annotations

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
