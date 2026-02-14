"""Unit tests for the adaptive retry layer."""
from __future__ import annotations

from openclaw_automation.adaptive import (
    AIRLINE_HINTS,
    Diagnosis,
    adapt_goal,
    diagnose,
    validate_result,
)


# ---------------------------------------------------------------------------
# diagnose() tests
# ---------------------------------------------------------------------------

class TestDiagnose:
    def test_captcha_not_retryable(self):
        result = {"ok": False, "error": "reCAPTCHA challenge detected", "result": None}
        d = diagnose("united", result)
        assert d.failure_type == "captcha"
        assert d.retryable is False

    def test_rate_limited_not_retryable(self):
        result = {"ok": False, "error": "429 Too Many Requests", "result": None}
        d = diagnose("delta", result)
        assert d.failure_type == "rate_limited"
        assert d.retryable is False

    def test_login_wall_from_stuck(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "stuck", "result": "The page is showing 'Sign in' dialog"},
        }
        d = diagnose("united", result)
        assert d.failure_type == "login_wall"
        assert d.retryable is True

    def test_page_crash(self):
        result = {"ok": False, "error": "Target closed: page crashed", "result": None}
        d = diagnose("delta", result)
        assert d.failure_type == "page_crash"
        assert d.retryable is True

    def test_max_steps_timeout(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "max_steps", "result": "Still loading..."},
        }
        d = diagnose("aeromexico", result)
        assert d.failure_type == "timeout"
        assert d.retryable is True

    def test_wrong_pricing_dollars_no_miles(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "success", "result": "Flight SFO-NRT $3,496 business class"},
        }
        d = diagnose("united", result)
        assert d.failure_type == "wrong_pricing"
        assert d.retryable is True

    def test_dollars_with_miles_not_wrong_pricing(self):
        """If both dollars and miles are present, it's not wrong_pricing."""
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "success", "result": "Flight: 80,000 miles + $5.60 tax"},
        }
        d = diagnose("united", result)
        # Should NOT be wrong_pricing since miles are present
        assert d.failure_type != "wrong_pricing"

    def test_empty_results(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "success", "result": "No flights available for this date"},
        }
        d = diagnose("delta", result)
        assert d.failure_type == "empty_results"
        assert d.retryable is True

    def test_element_not_found(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "stuck", "result": "Could not find the 'Shop with Miles' element not found"},
        }
        d = diagnose("delta", result)
        assert d.failure_type == "element_not_found"
        assert d.retryable is True

    def test_generic_error(self):
        result = {"ok": False, "error": "import failed: no module named foo", "result": None}
        d = diagnose("united", result)
        assert d.failure_type == "unknown"
        assert d.retryable is True

    def test_stuck_generic(self):
        result = {
            "ok": True,
            "error": None,
            "result": {"status": "stuck", "result": "Something went wrong"},
        }
        d = diagnose("aeromexico", result)
        assert d.failure_type == "stuck"
        assert d.retryable is True


# ---------------------------------------------------------------------------
# adapt_goal() tests
# ---------------------------------------------------------------------------

class TestAdaptGoal:
    def test_prepends_warning(self):
        original = "Search for flights SFO to NRT"
        diag = Diagnosis("login_wall", "Login required", retryable=True)
        adapted = adapt_goal(original, diag, "united")
        assert "WARNING" in adapted
        assert "sign-in" in adapted.lower() or "sign in" in adapted.lower()
        assert original in adapted

    def test_appends_airline_hints(self):
        original = "Search for Delta flights"
        diag = Diagnosis("wrong_pricing", "Cash prices shown", retryable=True)
        adapted = adapt_goal(original, diag, "delta")
        assert "Shop with Miles" in adapted
        assert "KNOWN ISSUES" in adapted

    def test_original_goal_preserved(self):
        original = "STEP 1: Do something\nSTEP 2: Do another thing"
        diag = Diagnosis("page_crash", "Page crashed", retryable=True)
        adapted = adapt_goal(original, diag, "aeromexico")
        assert "STEP 1: Do something" in adapted
        assert "STEP 2: Do another thing" in adapted

    def test_unknown_airline_no_hints(self):
        original = "Search for flights"
        diag = Diagnosis("timeout", "Timed out", retryable=True)
        adapted = adapt_goal(original, diag, "nonexistent_airline")
        assert original in adapted
        assert "KNOWN ISSUES" not in adapted


# ---------------------------------------------------------------------------
# validate_result() tests
# ---------------------------------------------------------------------------

class TestValidateResult:
    def test_united_valid_miles(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "FLIGHT: 7:15 AM-2:15 PM | 100,000 miles | 1 stop | business",
            },
        }
        valid, reason = validate_result("united", result, {})
        assert valid is True

    def test_united_combo_pricing_invalid(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "Flight: $1,666 + 183,000 miles combo only",
            },
        }
        valid, reason = validate_result("united", result, {})
        assert valid is False
        assert "combo" in reason.lower()

    def test_united_dollar_only_invalid(self):
        """United showing only dollars is caught by diagnose, not validate.
        validate_result checks for combo pricing specifically."""
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "Flight SFO-NRT $3,496",
            },
        }
        # No miles mentioned at all — but also no combo pattern
        # This passes validate but diagnose() would catch it as wrong_pricing
        valid, _ = validate_result("united", result, {})
        # It should still pass validate because there's no combo pattern
        # The diagnose() layer handles the dollar-only case
        assert valid is True

    def test_delta_valid_miles(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "CALENDAR: Mar 15 | 30,500 miles | Nonstop",
            },
        }
        valid, reason = validate_result("delta", result, {})
        assert valid is True

    def test_delta_dollars_only_invalid(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "Flight SFO-BOS $198 main cabin",
            },
        }
        valid, reason = validate_result("delta", result, {})
        assert valid is False
        assert "dollar" in reason.lower()

    def test_aeromexico_valid_cash(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "Vuelo MEX-CUN $2,500 MXN economia",
            },
        }
        valid, reason = validate_result("aeromexico", result, {})
        assert valid is True

    def test_aeromexico_points_invalid(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "FLIGHT: 08:00-14:30 | 18,000 puntos | Directo",
            },
        }
        valid, reason = validate_result("aeromexico", result, {})
        assert valid is False

    def test_singapore_valid_miles(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "Available: 148,000 miles SFO-SIN business",
            },
        }
        valid, reason = validate_result("singapore", result, {})
        assert valid is True

    def test_non_success_status_invalid(self):
        result = {
            "ok": True,
            "result": {
                "status": "stuck",
                "result": "100,000 miles available",
            },
        }
        valid, reason = validate_result("united", result, {})
        assert valid is False
        assert "stuck" in reason

    def test_empty_result_invalid(self):
        result = {
            "ok": True,
            "result": {
                "status": "success",
                "result": "",
            },
        }
        valid, reason = validate_result("united", result, {})
        assert valid is False
        assert "Empty" in reason


# ---------------------------------------------------------------------------
# AIRLINE_HINTS coverage
# ---------------------------------------------------------------------------

class TestAirlineHints:
    def test_all_four_airlines_have_hints(self):
        for airline in ("united", "delta", "aeromexico", "singapore"):
            assert airline in AIRLINE_HINTS
            assert len(AIRLINE_HINTS[airline]) >= 2
