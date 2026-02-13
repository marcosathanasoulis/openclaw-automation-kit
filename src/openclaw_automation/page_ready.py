"""Page readiness utilities for browser automation.

Prefer polling for explicit DOM-ready signals over fixed sleeps.
Falls back gracefully when networkidle is not achievable.
"""
from __future__ import annotations

import time


def wait_ready(page, timeout_ms: int = 5000, settle_ms: int = 300) -> None:
    """Wait for page readiness: networkidle -> domcontentloaded fallback -> settle.

    Args:
        page: Playwright Page object.
        timeout_ms: Max time to wait for networkidle (ms).
        settle_ms: Additional settle time after load state resolves (ms).
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=2000)
        except Exception:
            pass
    time.sleep(settle_ms / 1000)


def wait_for_selector(page, selector: str, timeout_ms: int = 10000, state: str = "visible") -> bool:
    """Wait for a specific DOM element to appear.

    Args:
        page: Playwright Page object.
        selector: CSS selector to wait for.
        timeout_ms: Max wait time (ms).
        state: Element state to wait for ('visible', 'attached', 'hidden').

    Returns:
        True if element found, False if timeout.
    """
    try:
        page.wait_for_selector(selector, timeout=timeout_ms, state=state)
        return True
    except Exception:
        return False
