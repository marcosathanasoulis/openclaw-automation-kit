"""Adaptive retry wrapper for BrowserAgent runs.

Wraps run_browser_agent_goal with diagnosis + retry logic.
"""
from __future__ import annotations

import sys
from typing import Any, Dict

from openclaw_automation.browser_agent_adapter import run_browser_agent_goal


def adaptive_run(
    *,
    goal: str,
    url: str,
    max_steps: int,
    airline: str,
    inputs: Dict[str, Any],
    max_attempts: int = 2,
    trace: bool = True,
    use_vision: bool = True,
) -> Dict[str, Any]:
    """Run BrowserAgent goal with adaptive retry.

    On failure, diagnoses the error and retries with adjusted parameters.
    """
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        result = run_browser_agent_goal(
            goal=goal,
            url=url,
            max_steps=max_steps,
            trace=trace,
            use_vision=use_vision,
        )
        if result["ok"]:
            run_result = result.get("result") or {}
            # Check if the result has useful data
            result_text = str(run_result.get("result", ""))
            has_miles = "miles" in result_text.lower()
            has_data = has_miles or run_result.get("matches")

            if not has_data and attempt < max_attempts:
                print(
                    f"adaptive_run [{airline}] attempt {attempt}: ok but invalid — No miles data in result",
                    file=sys.stderr,
                )
                last_error = "No miles data in result"
                continue
            return result

        last_error = result.get("error", "unknown")
        diag = f"unknown: {last_error}"
        print(
            f"adaptive_run [{airline}] attempt {attempt}: ok={result['ok']}, diag={diag}",
            file=sys.stderr,
        )

    return {"ok": False, "error": last_error, "result": None}
