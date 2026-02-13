from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .engine import AutomationEngine, pretty_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw automation toolkit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a script contract")
    p_validate.add_argument("--script-dir", required=True)

    p_run = sub.add_parser("run", help="Validate and run a script")
    p_run.add_argument("--script-dir", required=True)
    p_run.add_argument("--input", required=True, help="JSON object string")

    return parser.parse_args()


def _load_input(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--input must be a JSON object")
    return data


def _detect_repo_root(script_dir: Path) -> Path:
    candidates = [Path.cwd(), script_dir.resolve(), *script_dir.resolve().parents]
    for candidate in candidates:
        schema = candidate / "schemas" / "manifest.schema.json"
        if schema.exists():
            return candidate
    raise FileNotFoundError("Could not locate repository root with schemas/manifest.schema.json")


def main() -> None:
    args = _parse_args()
    script_dir = Path(args.script_dir).resolve()
    root = _detect_repo_root(script_dir)
    engine = AutomationEngine(root)

    if args.command == "validate":
        manifest = engine.validate_script(script_dir)
        print(pretty_json({"ok": True, "manifest": manifest}))
        return

    if args.command == "run":
        inputs = _load_input(args.input)
        result = engine.run(script_dir, inputs)
        print(pretty_json(result))
        return


if __name__ == "__main__":
    main()
