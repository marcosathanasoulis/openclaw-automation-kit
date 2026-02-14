from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .engine import AutomationEngine, pretty_json
from .nl import parse_query_to_run, resolve_script_dir


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw automation toolkit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a script automation spec")
    p_validate.add_argument("--script-dir", required=True)

    p_run = sub.add_parser("run", help="Validate and run a script")
    p_run.add_argument("--script-dir", required=True)
    p_run.add_argument("--input", required=True, help="JSON object string")

    p_query = sub.add_parser("run-query", help="Run from a plain-English query")
    p_query.add_argument("--query", required=True)
    cred_group = p_query.add_mutually_exclusive_group()
    cred_group.add_argument(
        "--credential-refs",
        default="{}",
        help="Optional JSON object of credential refs to merge into inputs",
    )
    cred_group.add_argument(
        "--credential-refs-file",
        help="Path to JSON file containing credential refs (safer than inline CLI JSON)",
    )
    cred_group.add_argument(
        "--credential-refs-env",
        help="Environment variable name holding JSON credential refs",
    )
    cred_group.add_argument(
        "--credential-refs-stdin",
        action="store_true",
        help="Read JSON credential refs from stdin",
    )

    return parser.parse_args()


def _load_input(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--input must be a JSON object")
    return data


def _load_credential_refs(args: argparse.Namespace) -> Dict[str, Any]:
    if getattr(args, "credential_refs_stdin", False):
        raw = sys.stdin.read().strip() or "{}"
        return _load_input(raw)
    if getattr(args, "credential_refs_file", None):
        raw = Path(args.credential_refs_file).read_text()
        return _load_input(raw)
    if getattr(args, "credential_refs_env", None):
        import os

        key = args.credential_refs_env
        raw = os.getenv(key, "{}")
        return _load_input(raw)
    return _load_input(getattr(args, "credential_refs", "{}"))


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
        if result.get("mode") == "placeholder":
            print(
                "WARNING: BrowserAgent not enabled. Results are placeholder data.",
                file=sys.stderr,
            )
        print(pretty_json(result))
        return

    if args.command == "run-query":
        parsed = parse_query_to_run(args.query)
        target_script_dir = resolve_script_dir(root, parsed.script_dir)
        credential_refs = _load_credential_refs(args)
        if credential_refs:
            parsed.inputs["credential_refs"] = credential_refs
        result = engine.run(target_script_dir, parsed.inputs)
        if result.get("mode") == "placeholder":
            print(
                "WARNING: BrowserAgent not enabled. Results are placeholder data.",
                file=sys.stderr,
            )
        print(pretty_json({"parsed_notes": parsed.notes, **result}))
        return


if __name__ == "__main__":
    main()
