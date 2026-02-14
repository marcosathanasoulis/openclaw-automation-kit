from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict


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

    The external BrowserAgent is expected to handle its own CDP locking
    internally (via CDPLock in _start_browser/_stop_browser). This adapter
    does NOT acquire a lock — doing so would deadlock since the same process
    would hold the lock when BrowserAgent tries to acquire it again.

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
    trace_env = os.getenv("OPENCLAW_BROWSER_TRACE", "").strip().lower()
    if trace_env in {"0", "false", "no", "off"}:
        trace = False

    if module_path:
        resolved = str(Path(module_path).expanduser().resolve())
        if resolved not in sys.path:
            sys.path.append(resolved)

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
