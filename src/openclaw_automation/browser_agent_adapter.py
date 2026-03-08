from __future__ import annotations

import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Any, Dict

SUCCESS_STATUSES = {"success"}
FAILURE_STATUSES = {"error", "stuck", "max_steps", "interrupted"}


def browser_agent_enabled() -> bool:
    return os.getenv("OPENCLAW_USE_BROWSER_AGENT", "").strip().lower() in {"1", "true", "yes", "on"}


def summarize_browser_agent_run(agent_run: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normalize adapter output so callers can reason about run status consistently."""
    payload = agent_run if isinstance(agent_run, dict) else {}
    run_result = payload.get("result")
    if not isinstance(run_result, dict):
        run_result = {}

    status = str(run_result.get("status", "unknown")).strip().lower() or "unknown"
    matches = run_result.get("matches", [])
    result_text = str(run_result.get("result", ""))
    has_content = bool(run_result) or bool(matches) or bool(result_text.strip())
    succeeded = bool(payload.get("ok")) and (
        status in SUCCESS_STATUSES or (status == "unknown" and has_content)
    )
    error = payload.get("error")
    if not error and status in FAILURE_STATUSES:
        error = f"BrowserAgent status: {status}"
    if not error and payload.get("ok") is False and status != "unknown":
        error = f"BrowserAgent status: {status}"

    return {
        "status": status,
        "steps": run_result.get("steps", "n/a"),
        "trace_dir": run_result.get("trace_dir", "n/a"),
        "review_url": run_result.get("review_url"),
        "current_url": run_result.get("current_url"),
        "matches": matches,
        "result_text": result_text,
        "result": run_result,
        "succeeded": succeeded,
        "error": error,
    }


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
    updates_env = os.getenv("OPENCLAW_BROWSER_SEND_UPDATES", "").strip().lower()
    if trace_env in {"0", "false", "no", "off"}:
        trace = False
    send_updates = updates_env in {"1", "true", "yes", "on"}
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
        init_signature = inspect.signature(agent_cls)
        init_kwargs = {
            "goal": goal,
            "url": url,
            "cdp_url": cdp_url,
            "max_steps": max_steps,
            "use_vision": use_vision,
            "trace": trace,
        }
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in init_signature.parameters.values()
        )
        if accepts_kwargs or "send_updates" in init_signature.parameters:
            init_kwargs["send_updates"] = send_updates
        agent = agent_cls(**init_kwargs)
        result = agent.run()
        payload = {"ok": True, "error": None, "result": result}
        summary = summarize_browser_agent_run(payload)
        if summary["succeeded"]:
            return payload

        failure_bits = [summary["error"] or "BrowserAgent returned an unsuccessful terminal status"]
        if summary["review_url"]:
            failure_bits.append(f"review_url={summary['review_url']}")
        if summary["current_url"]:
            failure_bits.append(f"current_url={summary['current_url']}")
        if summary["trace_dir"] not in {"", None, "n/a"}:
            failure_bits.append(f"trace_dir={summary['trace_dir']}")
        return {"ok": False, "error": "; ".join(failure_bits), "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"run failed: {exc}", "result": None}
