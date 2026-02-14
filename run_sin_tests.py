#!/usr/bin/env python3
"""Run United and SIA award searches to SIN sequentially via OpenClaw engine."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["OPENCLAW_USE_BROWSER_AGENT"] = "true"
os.environ["OPENCLAW_BROWSER_AGENT_MODULE"] = "browser_agent"
os.environ["OPENCLAW_BROWSER_AGENT_PATH"] = str(
    Path.home() / "athanasoulis-ai-assistant" / "src" / "browser"
)
os.environ["OPENCLAW_CDP_URL"] = "http://127.0.0.1:9222"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    from openclaw_automation.engine import AutomationEngine

    engine = AutomationEngine(ROOT)

    # Test 1: United to SIN
    print("=" * 60)
    print("TEST 1: United Award Search SFO -> SIN")
    print("=" * 60)
    united_result = engine.run(
        ROOT / "library" / "united_award",
        {
            "from": "SFO",
            "to": ["SIN"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )
    print(json.dumps(united_result, indent=2))
    print()

    # Test 2: SIA to SIN
    print("=" * 60)
    print("TEST 2: SIA KrisFlyer Award Search SFO -> SIN")
    print("=" * 60)
    sia_result = engine.run(
        ROOT / "library" / "singapore_award",
        {
            "from": "SFO",
            "to": ["SIN"],
            "days_ahead": 7,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )
    print(json.dumps(sia_result, indent=2))

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for label, result in [("United", united_result), ("SIA", sia_result)]:
        ok = result.get("ok", False)
        mode = result.get("mode", "unknown")
        status = "unknown"
        if result.get("result"):
            for obs in result["result"].get("raw_observations", []):
                if "BrowserAgent status:" in obs:
                    status = obs.split(":")[-1].strip()
        print(f"  {label}: ok={ok}, mode={mode}, status={status}")


if __name__ == "__main__":
    main()
