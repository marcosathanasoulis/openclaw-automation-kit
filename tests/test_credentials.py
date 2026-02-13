from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_credential_refs_resolution_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_SECRET_OPENCLAW_UNITED_USERNAME", "demo-user")
    monkeypatch.setenv("OPENCLAW_SECRET_OPENCLAW_UNITED_PASSWORD", "demo-pass")

    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "examples" / "united_award",
        {
            "from": "SFO",
            "to": ["AMS"],
            "days_ahead": 30,
            "max_miles": 120000,
            "travelers": 1,
            "cabin": "economy",
            "credential_refs": {
                "airline_username": "openclaw/united/username",
                "airline_password": "openclaw/united/password",
            },
        },
    )
    status = result["credential_status"]
    assert status["resolved_keys"] == ["airline_password", "airline_username"]
    assert status["unresolved_refs"] == {}

