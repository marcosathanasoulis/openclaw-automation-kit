from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_github_signin_check_emits_2fa_event() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "examples" / "github_signin_check",
        {
            "username": "demo-user",
            "credential_refs": {"password": "openclaw/github/password"},
            "messaging_target": {"type": "imessage", "address": "+14155550123"},
        },
    )
    payload = result["result"]
    assert payload["status"] == "needs_human_input"
    assert payload["events"]
    assert payload["events"][0]["event"] == "SECOND_FACTOR_REQUIRED"

