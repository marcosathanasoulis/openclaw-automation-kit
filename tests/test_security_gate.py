from __future__ import annotations

import time
from pathlib import Path

from openclaw_automation.engine import AutomationEngine
from openclaw_automation.security_gate import (
    create_signed_assertion,
    generate_totp_code,
    verify_totp_code,
)


def _risky_inputs() -> dict:
    return {
        "username": "demo-user",
        "credential_refs": {"password": "openclaw/github/password"},
        "messaging_target": {"type": "imessage", "address": "+14155550123"},
    }


def test_security_gate_disabled_allows_risky_run(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    monkeypatch.delenv("OPENCLAW_SECURITY_GATE_ENABLED", raising=False)

    result = engine.run(root / "library" / "github_signin_check", _risky_inputs())
    assert result["ok"] is True
    assert result["security_gate"]["allowed"] is True


def test_security_gate_blocks_risky_run_without_assertion(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    monkeypatch.setenv("OPENCLAW_SECURITY_GATE_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_SECURITY_SIGNING_KEY", "unit-test-signing-key")
    monkeypatch.setenv("OPENCLAW_SECURITY_EXPECTED_USER_ID", "+14152268266")

    result = engine.run(root / "library" / "github_signin_check", _risky_inputs())
    assert result["ok"] is False
    assert "missing security_assertion" in result["error"]
    assert result["security_gate"]["required"] is True


def test_security_gate_allows_valid_signed_assertion(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    signing_key = "unit-test-signing-key"
    monkeypatch.setenv("OPENCLAW_SECURITY_GATE_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_SECURITY_SIGNING_KEY", signing_key)
    monkeypatch.setenv("OPENCLAW_SECURITY_EXPECTED_USER_ID", "+14152268266")
    monkeypatch.setenv("OPENCLAW_SECURITY_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60))

    assertion = create_signed_assertion(
        user_id="+14152268266",
        signing_key=signing_key,
        ttl_seconds=7 * 24 * 60 * 60,
    )
    inputs = _risky_inputs()
    inputs["security_assertion"] = assertion

    result = engine.run(root / "library" / "github_signin_check", inputs)
    assert result["ok"] is True
    assert result["security_gate"]["allowed"] is True


def test_security_gate_rejects_expired_or_wrong_user(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    signing_key = "unit-test-signing-key"
    monkeypatch.setenv("OPENCLAW_SECURITY_GATE_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_SECURITY_SIGNING_KEY", signing_key)
    monkeypatch.setenv("OPENCLAW_SECURITY_EXPECTED_USER_ID", "+14152268266")
    monkeypatch.setenv("OPENCLAW_SECURITY_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60))

    expired = create_signed_assertion(
        user_id="+14152268266",
        signing_key=signing_key,
        verified_at=int(time.time()) - (9 * 24 * 60 * 60),
        expires_at=int(time.time()) - 1,
    )
    bad_user = create_signed_assertion(
        user_id="+14150001111",
        signing_key=signing_key,
        ttl_seconds=7 * 24 * 60 * 60,
    )

    inputs = _risky_inputs()
    inputs["security_assertion"] = expired
    result_expired = engine.run(root / "library" / "github_signin_check", inputs)
    assert result_expired["ok"] is False
    assert "expired" in result_expired["error"] or "older than allowed window" in result_expired["error"]

    inputs["security_assertion"] = bad_user
    result_bad_user = engine.run(root / "library" / "github_signin_check", inputs)
    assert result_bad_user["ok"] is False
    assert "does not match expected user" in result_bad_user["error"]


def test_totp_verification_helper_accepts_current_code() -> None:
    secret = "JBSWY3DPEHPK3PXP"
    now = int(time.time())
    code = generate_totp_code(secret=secret, for_unix_ts=now, period_seconds=30, digits=6)
    assert verify_totp_code(secret=secret, code=code, now_ts=now)


def test_security_gate_rejects_session_binding_mismatch(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    signing_key = "unit-test-signing-key"
    monkeypatch.setenv("OPENCLAW_SECURITY_GATE_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_SECURITY_SIGNING_KEY", signing_key)
    monkeypatch.setenv("OPENCLAW_SECURITY_EXPECTED_USER_ID", "+14152268266")
    monkeypatch.setenv("OPENCLAW_SECURITY_EXPECTED_SESSION_BINDING", "mac-mini:marcos")

    wrong_binding = create_signed_assertion(
        user_id="+14152268266",
        signing_key=signing_key,
        ttl_seconds=7 * 24 * 60 * 60,
        session_binding="home-mind:marcos",
    )
    ok_binding = create_signed_assertion(
        user_id="+14152268266",
        signing_key=signing_key,
        ttl_seconds=7 * 24 * 60 * 60,
        session_binding="mac-mini:marcos",
    )

    inputs = _risky_inputs()
    inputs["security_assertion"] = wrong_binding
    blocked = engine.run(root / "library" / "github_signin_check", inputs)
    assert blocked["ok"] is False
    assert "session binding mismatch" in blocked["error"]

    inputs["security_assertion"] = ok_binding
    allowed = engine.run(root / "library" / "github_signin_check", inputs)
    assert allowed["ok"] is True
