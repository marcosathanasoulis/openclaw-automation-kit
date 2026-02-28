from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict


def browser_agent_enabled() -> bool:
    return os.getenv("OPENCLAW_USE_BROWSER_AGENT", "").strip().lower() in {"1", "true", "yes", "on"}


def _restart_chrome(cdp_url: str) -> None:
    """Kill and restart Chrome when CDP protocol is frozen.

    Uses /tmp/launch_chrome_cdp.sh if it exists, otherwise platform-specific fallback.
    Waits up to 30s for Chrome to become responsive.
    """
    print("[browser_agent_adapter] Chrome appears frozen — restarting...", file=sys.stderr)

    launch_script = Path("/tmp/launch_chrome_cdp.sh")
    if sys.platform == "darwin" and launch_script.exists():
        subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
        time.sleep(3)
        subprocess.Popen(["bash", str(launch_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "darwin":
        # Fallback: restart Chrome directly
        port = cdp_url.rstrip("/").rsplit(":", 1)[-1]
        user_data = str(Path.home() / "Library/Application Support/Google Chrome")
        subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
        time.sleep(3)
        subprocess.Popen([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data}",
            "--no-first-run", "--no-default-browser-check",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # Linux (home-mind)
        subprocess.run(["pkill", "-f", "google-chrome"], capture_output=True)
        subprocess.run(["pkill", "-f", "chromium"], capture_output=True)
        time.sleep(3)
        start_script = Path("/tmp/start_chrome_real.sh")
        if start_script.exists():
            subprocess.Popen(["bash", str(start_script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for Chrome to become responsive (up to 35s)
    version_url = cdp_url.rstrip("/") + "/json/version"
    for _ in range(35):
        time.sleep(1)
        try:
            urllib.request.urlopen(version_url, timeout=2)
            print("[browser_agent_adapter] Chrome restarted and responsive.", file=sys.stderr)
            return
        except Exception:
            pass
    print("[browser_agent_adapter] Warning: Chrome may not be fully ready after restart.", file=sys.stderr)
    time.sleep(3)


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

    for attempt in range(2):
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
            err_str = str(exc)
            # Detect frozen Chrome: WebSocket connects but protocol hangs
            if attempt == 0 and "connect_over_cdp" in err_str and "Timeout" in err_str:
                _restart_chrome(cdp_url)
                continue
            return {"ok": False, "error": f"run failed: {exc}", "result": None}

    return {"ok": False, "error": "run failed: max retries exceeded", "result": None}
