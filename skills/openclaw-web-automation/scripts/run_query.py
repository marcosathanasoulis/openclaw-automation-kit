#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run unified web automation query")
    parser.add_argument("--query", required=True, help="Natural-language automation request")
    parser.add_argument(
        "--credential-refs",
        default="{}",
        help="JSON object mapping logical credential fields to refs (less safe; prefer --credential-refs-file or --credential-refs-env)",
    )
    parser.add_argument(
        "--credential-refs-file",
        default="",
        help="Path to JSON file with credential refs (safer than inline args)",
    )
    parser.add_argument(
        "--credential-refs-env",
        default="",
        help="Env var containing JSON credential refs (safer than inline args)",
    )
    parser.add_argument(
        "--notify-imessage",
        default="",
        help="Optional phone/chat GUID for BlueBubbles notification",
    )
    parser.add_argument(
        "--send-notification",
        action="store_true",
        help="Actually send iMessage notification (default is dry run)",
    )
    return parser.parse_args()


def _find_repo_root() -> Path | None:
    schema_rel = Path("schemas/manifest.schema.json")
    env_root = os.getenv("OPENCLAW_AUTOMATION_ROOT", "").strip()
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if (p / schema_rel).exists():
            return p

    in_repo = Path(__file__).resolve().parents[3]
    if (in_repo / schema_rel).exists():
        return in_repo

    cur = Path.cwd().resolve()
    for c in [cur, *cur.parents]:
        if (c / schema_rel).exists():
            return c
    return None


def _run_query(root: Path, query: str, args: argparse.Namespace) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "openclaw_automation.cli",
        "run-query",
        "--query",
        query,
    ]
    stdin_payload: str | None = None
    if args.credential_refs_file:
        cmd.extend(["--credential-refs-file", args.credential_refs_file])
    elif args.credential_refs_env:
        cmd.extend(["--credential-refs-env", args.credential_refs_env])
    elif args.credential_refs and args.credential_refs.strip() not in {"", "{}"}:
        # Avoid placing credential refs in subprocess argv; pass via stdin.
        cmd.append("--credential-refs-stdin")
        stdin_payload = args.credential_refs
    retryable_markers = (
        "rate limit",
        "temporarily unavailable",
        "timeout",
        "connection reset",
    )
    last_error: str | None = None
    for attempt in range(1, 4):
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, input=stdin_payload)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        message = proc.stderr.strip() or proc.stdout.strip() or "run-query failed"
        last_error = message
        if attempt < 3 and any(marker in message.lower() for marker in retryable_markers):
            time.sleep(2**attempt)
            continue
        break
    raise RuntimeError(last_error or "run-query failed")


def _notify_imessage(target: str, summary: str) -> None:
    try:
        from connectors.imessage_bluebubbles.webhook_example import send_imessage
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("BlueBubbles connector is not installed/configured") from exc
    send_imessage(target, summary)


def _extract_summary(result: dict) -> str:
    inner = result.get("result")
    if isinstance(inner, dict):
        summary = inner.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    return "Automation query completed."


def main() -> int:
    args = _parse_args()
    root = _find_repo_root()
    if root is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "Could not locate OpenClaw Automation Kit root. "
                        "Set OPENCLAW_AUTOMATION_ROOT and ensure `pip install -e .` has been run."
                    ),
                },
                indent=2,
            )
        )
        return 2

    try:
        result = _run_query(root, args.query, args)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    summary = _extract_summary(result)
    status = {
        "ok": True,
        "summary": summary,
        "script_id": result.get("script_id"),
        "mode": result.get("mode"),
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
            status["notification"] = f"dry-run to {args.notify_imessage} (pass --send-notification to send)"

    print(json.dumps({"status": status, "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
