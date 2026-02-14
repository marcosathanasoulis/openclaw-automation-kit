#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[3]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenClaw universal memory launcher")
    p.add_argument("--action", required=True, choices=["init-schema", "ingest-json", "search"])
    p.add_argument("--dsn", required=True)
    p.add_argument("--source")
    p.add_argument("--account")
    p.add_argument("--entity-type")
    p.add_argument("--input")
    p.add_argument("--query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--cursor", default="")
    p.add_argument("--id-field", default="id")
    p.add_argument("--title-field", default="title")
    p.add_argument("--body-field", default="body")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    repo_root = _find_repo_root()

    base = [sys.executable, "-m", "openclaw_memory.cli", args.action, "--dsn", args.dsn]
    if args.action == "ingest-json":
        required = {
            "source": args.source,
            "account": args.account,
            "entity_type": args.entity_type,
            "input": args.input,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            print(json.dumps({"ok": False, "error": f"Missing required args: {', '.join(missing)}"}, indent=2))
            raise SystemExit(2)
        base.extend(
            [
                "--source",
                args.source,
                "--account",
                args.account,
                "--entity-type",
                args.entity_type,
                "--input",
                args.input,
                "--limit",
                str(args.limit),
                "--cursor",
                args.cursor,
                "--id-field",
                args.id_field,
                "--title-field",
                args.title_field,
                "--body-field",
                args.body_field,
            ]
        )
    elif args.action == "search":
        if not args.query:
            print(json.dumps({"ok": False, "error": "Missing required arg: --query"}, indent=2))
            raise SystemExit(2)
        base.extend(["--query", args.query, "--limit", str(args.limit)])

    result = subprocess.run(base, cwd=repo_root, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
