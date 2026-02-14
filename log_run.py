#!/usr/bin/env python3
"""
Run log utility for openclaw-automation-kit.

Append mode:
    python log_run.py --script-id "delta.award_search" --status pass \
                      --duration 45.2 --notes "found 3 flights" --agent opus

Cooldown check mode:
    python log_run.py --check-cooldown "singapore.award_search" --min-gap 300
    Exit code 0 = OK to run, 1 = too soon (prints seconds remaining).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "status"
LOG_FILE = LOG_DIR / "run_log.jsonl"


def append_run(script_id: str, status: str, duration: float, notes: str, agent: str) -> None:
    """Append a single run record to the JSONL log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script_id": script_id,
        "status": status,
        "duration_seconds": round(duration, 2),
        "notes": notes,
        "agent": agent,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    sid = entry["script_id"]
    st = entry["status"]
    dur = entry["duration_seconds"]
    print(f"Logged: {sid} [{st}] {dur}s")


def check_cooldown(script_id: str, min_gap: float) -> int:
    """
    Check whether enough time has elapsed since the last run of script_id.

    Returns 0 if OK to proceed, 1 if still in cooldown.
    """
    if not LOG_FILE.exists():
        print(f"No previous runs found for {script_id}. OK to run.")
        return 0

    last_ts = None
    with open(LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("script_id") == script_id:
                last_ts = record.get("timestamp_utc")

    if last_ts is None:
        print(f"No previous runs found for {script_id}. OK to run.")
        return 0

    # Parse the timestamp -- handle both Z suffix and +00:00
    last_ts_clean = last_ts.replace("Z", "+00:00")
    last_dt = datetime.fromisoformat(last_ts_clean)
    now_dt = datetime.now(timezone.utc)
    elapsed = (now_dt - last_dt).total_seconds()

    if elapsed >= min_gap:
        print(f"Cooldown OK for {script_id}. Last run {elapsed:.0f}s ago (min gap {min_gap:.0f}s).")
        return 0
    else:
        remaining = min_gap - elapsed
        print(f"Too soon for {script_id}. Last run {elapsed:.0f}s ago, need {min_gap:.0f}s. "
              f"{remaining:.0f}s remaining.")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="openclaw-automation-kit run logger")

    # --- Append mode arguments ---
    parser.add_argument("--script-id", type=str, help="Identifier for the automation script")
    parser.add_argument("--status", type=str, choices=["pass", "fail", "error"],
                        help="Run outcome: pass, fail, or error")
    parser.add_argument("--duration", type=float, help="Run duration in seconds")
    parser.add_argument("--notes", type=str, default="", help="Free-text notes about the run")
    parser.add_argument("--agent", type=str, default="unknown", help="Who/what triggered the run")

    # --- Cooldown check arguments ---
    parser.add_argument("--check-cooldown", type=str, metavar="SCRIPT_ID",
                        help="Check cooldown for a given script_id (mutually exclusive with append)")
    parser.add_argument("--min-gap", type=float, default=300,
                        help="Minimum seconds between runs (default: 300)")

    args = parser.parse_args()

    # Cooldown mode
    if args.check_cooldown:
        rc = check_cooldown(args.check_cooldown, args.min_gap)
        sys.exit(rc)

    # Append mode -- require the mandatory fields
    if not args.script_id:
        parser.error("--script-id is required for logging a run")
    if not args.status:
        parser.error("--status is required for logging a run")
    if args.duration is None:
        parser.error("--duration is required for logging a run")

    append_run(args.script_id, args.status, args.duration, args.notes, args.agent)


if __name__ == "__main__":
    main()
