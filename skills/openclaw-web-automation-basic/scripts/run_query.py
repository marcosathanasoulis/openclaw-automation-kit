#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a public-site automation query")
    parser.add_argument("--query", required=True, help="Natural-language website task")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[3]
    cmd = [
        sys.executable,
        "-m",
        "openclaw_automation.cli",
        "run-query",
        "--query",
        args.query,
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip())
        return proc.returncode

    # Normalize output to compact JSON for tool users.
    try:
        parsed = json.loads(proc.stdout)
        print(json.dumps(parsed, indent=2))
    except Exception:
        print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
