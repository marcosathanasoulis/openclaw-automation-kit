from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List


@dataclass
class RunRequest:
    run_id: str
    script_id: str
    required_locks: List[str] = field(default_factory=list)


class LockManager:
    def __init__(self) -> None:
        self._held: Dict[str, str] = {}

    def try_acquire(self, run_id: str, locks: List[str]) -> bool:
        for lock in locks:
            owner = self._held.get(lock)
            if owner is not None and owner != run_id:
                return False
        for lock in locks:
            self._held[lock] = run_id
        return True

    def release(self, run_id: str) -> None:
        to_delete = [k for k, v in self._held.items() if v == run_id]
        for key in to_delete:
            del self._held[key]

    def held_locks(self) -> Dict[str, str]:
        return dict(self._held)


class RunQueue:
    def __init__(self, max_concurrent_runs: int = 1) -> None:
        if max_concurrent_runs < 1:
            raise ValueError("max_concurrent_runs must be >= 1")
        self.max_concurrent_runs = max_concurrent_runs
        self.queue: Deque[RunRequest] = deque()
        self.running: Dict[str, RunRequest] = {}
        self.locks = LockManager()

    def enqueue(self, req: RunRequest) -> None:
        self.queue.append(req)

    def tick(self) -> List[RunRequest]:
        started: List[RunRequest] = []
        if len(self.running) >= self.max_concurrent_runs:
            return started

        remaining: Deque[RunRequest] = deque()
        while self.queue and len(self.running) < self.max_concurrent_runs:
            req = self.queue.popleft()
            if self.locks.try_acquire(req.run_id, req.required_locks):
                self.running[req.run_id] = req
                started.append(req)
            else:
                remaining.append(req)

        while self.queue:
            remaining.append(self.queue.popleft())
        self.queue = remaining
        return started

    def complete(self, run_id: str) -> None:
        if run_id in self.running:
            del self.running[run_id]
        self.locks.release(run_id)

    def snapshot(self) -> Dict[str, object]:
        return {
            "queued": [r.run_id for r in self.queue],
            "running": list(self.running.keys()),
            "held_locks": self.locks.held_locks(),
            "max_concurrent_runs": self.max_concurrent_runs,
        }
