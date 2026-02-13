from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from .engine import AutomationEngine, pretty_json
from .nl import parse_query_to_run, resolve_script_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw automation toolkit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a script contract")
    p_validate.add_argument("--script-dir", required=True)

    p_run = sub.add_parser("run", help="Validate and run a script")
    p_run.add_argument("--script-dir", required=True)
    p_run.add_argument("--input", required=True, help="JSON object string")

    p_query = sub.add_parser("run-query", help="Run from a plain-English query")
    p_query.add_argument("--query", required=True)
    p_query.add_argument(
        "--credential-refs",
        default="{}",
        help="Optional JSON object of credential refs to merge into inputs",
    )

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
    if args.command in {"validate", "run"}:
        script_dir = Path(args.script_dir).resolve()
        root = _detect_repo_root(script_dir)
    else:
        root = _detect_repo_root(Path.cwd())
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

    if args.command == "run-query":
        parsed = parse_query_to_run(args.query)
        target_script_dir = resolve_script_dir(root, parsed.script_dir)
        credential_refs = _load_input(args.credential_refs)
        if credential_refs:
            parsed.inputs["credential_refs"] = credential_refs
        result = engine.run(target_script_dir, parsed.inputs)
        print(pretty_json({"parsed_notes": parsed.notes, **result}))
        return


if __name__ == "__main__":
    main()
