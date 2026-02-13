from __future__ import annotations

import json
import os
from pathlib import Path

from openclaw_automation.cdp_lock import CDPLock


def test_cdp_lock_acquire_release(tmp_path: Path) -> None:
    lock_file = tmp_path / "browser_cdp.lock"
    lock = CDPLock(lock_file=lock_file, timeout_seconds=2, retry_seconds=1, owner_pid=os.getpid())
    lock.acquire()
    assert lock_file.exists()
    lock.release()
    assert not lock_file.exists()


def test_cdp_lock_reaps_stale_pid(tmp_path: Path) -> None:
    lock_file = tmp_path / "browser_cdp.lock"
    # Write a dead PID to simulate stale lock.
    lock_file.write_text(json.dumps({"pid": 999999, "start_time": "2026-01-01T00:00:00Z"}))

    lock = CDPLock(lock_file=lock_file, timeout_seconds=2, retry_seconds=1, owner_pid=os.getpid())
    lock.acquire()
    assert lock_file.exists()
    owner = json.loads(lock_file.read_text())["pid"]
    assert owner == os.getpid()
    lock.release()
