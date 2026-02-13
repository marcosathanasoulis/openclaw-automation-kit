from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .cdp_lock import CDPLock


def browser_agent_enabled() -> bool:
    return os.getenv("OPENCLAW_USE_BROWSER_AGENT", "").strip().lower() in {"1", "true", "yes", "on"}


def run_browser_agent_goal(
    *,
    goal: str,
    url: str,
    max_steps: int,
    trace: bool = True,
    use_vision: bool = True,
) -> Dict[str, Any]:
    """Run an external BrowserAgent implementation, if available.

    Required runtime env:
    - OPENCLAW_USE_BROWSER_AGENT=true
    - OPENCLAW_BROWSER_AGENT_MODULE (default: browser_agent)
    Optional runtime env:
    - OPENCLAW_BROWSER_AGENT_PATH (directory to append to sys.path)
    - OPENCLAW_CDP_URL (default: http://127.0.0.1:9222)
    """
    module_name = os.getenv("OPENCLAW_BROWSER_AGENT_MODULE", "browser_agent").strip() or "browser_agent"
    module_path = os.getenv("OPENCLAW_BROWSER_AGENT_PATH", "").strip()
    cdp_url = os.getenv("OPENCLAW_CDP_URL", "http://127.0.0.1:9222").strip() or "http://127.0.0.1:9222"
    lock_file = Path(os.getenv("OPENCLAW_CDP_LOCK_FILE", "/tmp/browser_cdp.lock"))
    lock_timeout = int(os.getenv("OPENCLAW_CDP_LOCK_TIMEOUT", "600"))
    lock_retry = int(os.getenv("OPENCLAW_CDP_LOCK_RETRY_SECONDS", "5"))

    if module_path:
        resolved = str(Path(module_path).expanduser().resolve())
        if resolved not in sys.path:
            sys.path.append(resolved)

    lock = CDPLock(lock_file=lock_file, timeout_seconds=lock_timeout, retry_seconds=lock_retry)
    try:
        lock.acquire()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"cdp lock failed: {exc}", "result": None}

    try:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import failed: {exc}", "result": None}

        agent_cls = getattr(module, "BrowserAgent", None)
        if agent_cls is None:
            return {"ok": False, "error": f"BrowserAgent not found in module '{module_name}'", "result": None}

        try:
            agent = agent_cls(
                goal=goal,
                url=url,
                cdp_url=cdp_url,
                max_steps=max_steps,
                use_vision=use_vision,
                trace=trace,
            )
            result = agent.run()
            return {"ok": True, "error": None, "result": result}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"run failed: {exc}", "result": None}
    finally:
        lock.release()
