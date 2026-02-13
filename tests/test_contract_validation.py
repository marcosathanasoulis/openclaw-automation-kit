from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_example_manifests_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)

    for script in [
        "public_page_check",
        "united_award",
        "singapore_award",
        "ana_award",
        "bofa_alert",
        "github_signin_check",
    ]:
        manifest = engine.validate_script(root / "examples" / script)
        assert manifest["id"]
        assert manifest["entrypoint"] == "runner.py"
