#!/usr/bin/env python3
"""Comprehensive test suite for all OpenClaw automations.

Runs basic (no-browser) tests first, then browser tests sequentially via CDPLock.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ["OPENCLAW_USE_BROWSER_AGENT"] = "true"
os.environ["OPENCLAW_BROWSER_AGENT_MODULE"] = "browser_agent"
os.environ["OPENCLAW_BROWSER_AGENT_PATH"] = str(
    Path.home() / "athanasoulis-ai-assistant" / "src" / "browser"
)
os.environ["OPENCLAW_CDP_URL"] = "http://127.0.0.1:9222"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

RESULTS: list[dict] = []


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_test(name: str, script_dir: str, inputs: dict, needs_browser: bool = True) -> dict:
    from openclaw_automation.engine import AutomationEngine

    engine = AutomationEngine(ROOT)
    log(f"--- {name} ---")
    log(f"  Script: {script_dir}")
    log(f"  Inputs: {json.dumps(inputs)[:200]}")

    start = time.time()
    try:
        result = engine.run(ROOT / script_dir, inputs)
        elapsed = time.time() - start
        ok = result.get("ok", False)
        mode = result.get("mode", result.get("result", {}).get("mode", "unknown"))
        status = "unknown"

        if result.get("result"):
            for obs in result["result"].get("raw_observations", []):
                if "BrowserAgent status:" in obs:
                    status = obs.split(":")[-1].strip()

        entry = {
            "name": name,
            "ok": ok,
            "mode": mode,
            "status": status,
            "elapsed_s": round(elapsed, 1),
            "error": result.get("error"),
        }
        RESULTS.append(entry)
        emoji = "PASS" if ok else "FAIL"
        log(f"  {emoji}: ok={ok}, mode={mode}, status={status}, {elapsed:.1f}s")
        if not ok:
            log(f"  Error: {result.get('error', 'none')}")
        return result
    except Exception as exc:
        elapsed = time.time() - start
        entry = {
            "name": name,
            "ok": False,
            "mode": "error",
            "status": "exception",
            "elapsed_s": round(elapsed, 1),
            "error": str(exc),
        }
        RESULTS.append(entry)
        log(f"  EXCEPTION: {exc}")
        return {"ok": False, "error": str(exc)}


def main() -> None:
    log("=" * 60)
    log("COMPREHENSIVE TEST SUITE: OpenClaw Automation Kit")
    log(f"Started: {datetime.now().isoformat()}")
    log("=" * 60)

    # ── Phase 1: Basic tests (no browser) ──

    log("")
    log("PHASE 1: Basic Tests (no browser required)")
    log("-" * 40)

    # Public page check
    run_test(
        "Public page check (Yahoo)",
        "examples/public_page_check",
        {"url": "https://www.yahoo.com", "keyword": "news"},
        needs_browser=False,
    )

    # GitHub signin check (placeholder)
    run_test(
        "GitHub signin check (placeholder)",
        "library/github_signin_check",
        {
            "username": "testuser",
            "credential_refs": {
                "password": "openclaw/github/password",
            },
        },
        needs_browser=False,
    )

    # United placeholder
    os.environ["OPENCLAW_USE_BROWSER_AGENT"] = "false"
    run_test(
        "United award (placeholder)",
        "library/united_award",
        {
            "from": "SFO",
            "to": ["NRT"],
            "days_ahead": 14,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
        needs_browser=False,
    )

    # SIA placeholder
    run_test(
        "SIA award (placeholder)",
        "library/singapore_award",
        {
            "from": "SFO",
            "to": ["SIN"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
        needs_browser=False,
    )

    # ANA placeholder
    run_test(
        "ANA award (placeholder)",
        "library/ana_award",
        {
            "from": "SFO",
            "to": ["NRT"],
            "days_ahead": 30,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
        needs_browser=False,
    )

    # AeroMexico placeholder
    run_test(
        "AeroMexico award (placeholder)",
        "library/aeromexico_award",
        {
            "from": "SFO",
            "to": ["MEX"],
            "days_ahead": 14,
            "max_miles": 80000,
            "travelers": 2,
            "cabin": "business",
        },
        needs_browser=False,
    )

    # BofA placeholder
    run_test(
        "BofA alert (placeholder)",
        "library/bofa_alert",
        {"query": "check balances"},
        needs_browser=False,
    )

    # Chase placeholder
    run_test(
        "Chase balance (placeholder)",
        "library/chase_balance",
        {"check_type": "ur_points"},
        needs_browser=False,
    )

    # ── Phase 2: Browser tests ──
    os.environ["OPENCLAW_USE_BROWSER_AGENT"] = "true"

    log("")
    log("PHASE 2: Browser Tests (CDPLock required, sequential)")
    log("-" * 40)

    # United browser test
    run_test(
        "United award (BROWSER)",
        "library/united_award",
        {
            "from": "SFO",
            "to": ["SIN"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )

    # BofA browser test
    run_test(
        "BofA alert (BROWSER)",
        "library/bofa_alert",
        {"query": "check all account balances"},
    )

    # ANA browser test
    run_test(
        "ANA award (BROWSER)",
        "library/ana_award",
        {
            "from": "SFO",
            "to": ["NRT"],
            "days_ahead": 30,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )

    # AeroMexico browser test
    run_test(
        "AeroMexico award (BROWSER)",
        "library/aeromexico_award",
        {
            "from": "SFO",
            "to": ["MEX"],
            "days_ahead": 14,
            "max_miles": 80000,
            "travelers": 2,
            "cabin": "business",
        },
    )

    # Chase browser test — SKIPPED (requires push 2FA, user must be present)
    log("  SKIP: Chase balance (BROWSER) — push 2FA requires user presence")

    # SIA browser test
    run_test(
        "SIA award (BROWSER)",
        "library/singapore_award",
        {
            "from": "SFO",
            "to": ["SIN"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )

    # ── Summary ──
    log("")
    log("=" * 60)
    log("RESULTS SUMMARY")
    log("=" * 60)

    passed = sum(1 for r in RESULTS if r["ok"])
    total = len(RESULTS)

    for r in RESULTS:
        icon = "PASS" if r["ok"] else "FAIL"
        log(f"  [{icon}] {r['name']}: mode={r['mode']}, {r['elapsed_s']}s")
        if r.get("error"):
            log(f"         Error: {r['error'][:100]}")

    log(f"\nTotal: {passed}/{total} passed")
    log(f"Finished: {datetime.now().isoformat()}")

    # Write JSON results
    results_path = ROOT / "test_results.json"
    with open(results_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total": total,
                "passed": passed,
                "results": RESULTS,
            },
            f,
            indent=2,
        )
    log(f"Results saved to {results_path}")


if __name__ == "__main__":
    main()
