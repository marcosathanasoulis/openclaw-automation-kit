from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOCK_PATH = Path.home() / ".openclaw" / "browser_cdp.lock"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user.
        return True


@dataclass
class CDPLock:
    lock_file: Path
    timeout_seconds: int = 600
    retry_seconds: int = 5
    owner_pid: int = os.getpid()

    def acquire(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + max(1, self.timeout_seconds)

        while True:
            try:
                fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    payload = {
                        "pid": self.owner_pid,
                        "start_time": datetime.now(timezone.utc).isoformat(),
                    }
                    os.write(fd, json.dumps(payload).encode("utf-8"))
                finally:
                    os.close(fd)
                return
            except FileExistsError:
                if self._reap_if_stale():
                    continue

                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for CDP lock: {self.lock_file} (timeout={self.timeout_seconds}s)"
                    )
                time.sleep(max(1, self.retry_seconds))

    def release(self) -> None:
        if not self.lock_file.exists():
            return

        owner_pid = self._read_pid()
        if owner_pid != self.owner_pid:
            return
        try:
            self.lock_file.unlink()
        except FileNotFoundError:
            return

    def _read_pid(self) -> int | None:
        try:
            data = json.loads(self.lock_file.read_text())
        except Exception:  # noqa: BLE001
            return None
        pid = data.get("pid")
        if isinstance(pid, int):
            return pid
        try:
            return int(pid)
        except Exception:  # noqa: BLE001
            return None

    def _reap_if_stale(self) -> bool:
        owner_pid = self._read_pid()
        if owner_pid is None:
            try:
                self.lock_file.unlink()
                return True
            except FileNotFoundError:
                return True
            except Exception:  # noqa: BLE001
                return False

        if not _pid_alive(owner_pid):
            try:
                self.lock_file.unlink()
                return True
            except FileNotFoundError:
                return True
            except Exception:  # noqa: BLE001
                return False
        return False
