"""Tests for engine error handling, output validation, and placeholder mode."""
from pathlib import Path

from openclaw_automation.engine import AutomationEngine


def test_runner_exception_returns_structured_error(tmp_path: Path) -> None:
    """Runner that raises should return ok=False with error details."""
    root = Path(__file__).resolve().parents[1]
    # Create a minimal script that raises
    script_dir = tmp_path / "bad_script"
    script_dir.mkdir()
    (script_dir / "manifest.json").write_text(
        '{"id":"test.bad","version":"0.1.0","entrypoint":"runner.py",'
        '"inputs_schema":"schemas/input.json","outputs_schema":"schemas/output.json",'
        '"permissions":{"browser":false,"network_domains":[]},"requires_human_steps":[]}'
    )
    schemas = script_dir / "schemas"
    schemas.mkdir()
    (schemas / "input.json").write_text('{"type":"object"}')
    (schemas / "output.json").write_text('{"type":"object"}')
    (script_dir / "runner.py").write_text(
        "def run(context, inputs):\n    raise ValueError('test boom')\n"
    )

    engine = AutomationEngine(root)
    result = engine.run(script_dir, {})
    assert result["ok"] is False
    assert "test boom" in result["error"]


def test_runner_returning_non_dict_returns_error(tmp_path: Path) -> None:
    """Runner that returns a string instead of dict should get structured error."""
    root = Path(__file__).resolve().parents[1]
    script_dir = tmp_path / "str_script"
    script_dir.mkdir()
    (script_dir / "manifest.json").write_text(
        '{"id":"test.str","version":"0.1.0","entrypoint":"runner.py",'
        '"inputs_schema":"schemas/input.json","outputs_schema":"schemas/output.json",'
        '"permissions":{"browser":false,"network_domains":[]},"requires_human_steps":[]}'
    )
    schemas = script_dir / "schemas"
    schemas.mkdir()
    (schemas / "input.json").write_text('{"type":"object"}')
    (schemas / "output.json").write_text('{"type":"object"}')
    (script_dir / "runner.py").write_text(
        "def run(context, inputs):\n    return 'not a dict'\n"
    )

    engine = AutomationEngine(root)
    result = engine.run(script_dir, {})
    assert result["ok"] is False
    assert "must be a dict" in result["error"]


def test_placeholder_mode_surfaced_in_envelope(tmp_path: Path) -> None:
    """Runner returning mode=placeholder should surface placeholder=True in envelope."""
    root = Path(__file__).resolve().parents[1]
    script_dir = tmp_path / "placeholder_script"
    script_dir.mkdir()
    (script_dir / "manifest.json").write_text(
        '{"id":"test.placeholder","version":"0.1.0","entrypoint":"runner.py",'
        '"inputs_schema":"schemas/input.json","outputs_schema":"schemas/output.json",'
        '"permissions":{"browser":false,"network_domains":[]},"requires_human_steps":[]}'
    )
    schemas = script_dir / "schemas"
    schemas.mkdir()
    (schemas / "input.json").write_text('{"type":"object"}')
    (schemas / "output.json").write_text('{"type":"object"}')
    (script_dir / "runner.py").write_text(
        "def run(context, inputs):\n    return {'mode': 'placeholder', 'data': 'stub'}\n"
    )

    engine = AutomationEngine(root)
    result = engine.run(script_dir, {})
    assert result["ok"] is True
    assert result["placeholder"] is True
