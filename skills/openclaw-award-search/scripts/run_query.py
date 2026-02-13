#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run award-search query as an installable skill entrypoint")
    parser.add_argument("--query", required=True, help="Natural-language award search request")
    parser.add_argument(
        "--credential-refs",
        default="{}",
        help="JSON object mapping logical credential fields to refs",
    )
    parser.add_argument(
        "--notify-imessage",
        default="",
        help="Optional phone/chat GUID for BlueBubbles notification",
    )
    parser.add_argument(
        "--send-notification",
        action="store_true",
        help="Actually send iMessage notification (default is no send)",
    )
    return parser.parse_args()


def _run_query(root: Path, query: str, credential_refs: str) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "openclaw_automation.cli",
        "run-query",
        "--query",
        query,
        "--credential-refs",
        credential_refs,
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "run-query failed")
    return json.loads(proc.stdout)


def _notify_imessage(target: str, summary: str) -> None:
    # Deferred import so the skill can run without requests/connector setup.
    from connectors.imessage_bluebubbles.webhook_example import send_imessage

    send_imessage(target, summary)


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parents[3]

    try:
        result = _run_query(root, args.query, args.credential_refs)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    summary = result.get("result", {}).get("summary", "Award query completed.")
    status = {
        "ok": True,
        "summary": summary,
        "script_id": result.get("script_id"),
        "parsed_notes": result.get("parsed_notes", []),
        "notification": "not requested",
    }

    if args.notify_imessage:
        if args.send_notification:
            try:
                _notify_imessage(args.notify_imessage, summary)
                status["notification"] = f"sent to {args.notify_imessage}"
            except Exception as exc:  # noqa: BLE001
                status["notification"] = f"failed: {exc}"
        else:
            status["notification"] = (
                f"dry-run to {args.notify_imessage} (pass --send-notification to actually send)"
            )

    print(json.dumps({"status": status, "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
