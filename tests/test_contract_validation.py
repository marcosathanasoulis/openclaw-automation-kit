from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_library_and_example_manifests_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)

    for script_dir in [
        root / "examples" / "public_page_check",
        root / "library" / "united_award",
        root / "library" / "singapore_award",
        root / "library" / "ana_award",
        root / "library" / "bofa_alert",
        root / "library" / "github_signin_check",
        root / "skills" / "openclaw-award-search",
        root / "skills" / "openclaw-web-automation-basic",
    ]:
        manifest = engine.validate_script(script_dir)
        assert manifest["id"]
        assert manifest["entrypoint"] == "runner.py"
