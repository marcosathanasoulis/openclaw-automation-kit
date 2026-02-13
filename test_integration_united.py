#!/usr/bin/env python3
"""Integration test: United award search through the full OpenClaw skill pipeline.

Uses real BrowserAgent + CDPLock on Mac Mini.
Tests the complete chain: skill runner → NL parser → engine → United library runner → BrowserAgent adapter → Chrome.
"""
import json
import os
import sys
from pathlib import Path

# Setup env for BrowserAgent integration
os.environ["OPENCLAW_USE_BROWSER_AGENT"] = "true"
os.environ["OPENCLAW_BROWSER_AGENT_MODULE"] = "browser_agent"
os.environ["OPENCLAW_BROWSER_AGENT_PATH"] = str(Path.home() / "athanasoulis-ai-assistant" / "src" / "browser")
os.environ["OPENCLAW_CDP_URL"] = "http://127.0.0.1:9222"
os.environ["OPENCLAW_CDP_LOCK_FILE"] = "/tmp/browser_cdp.lock"
os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

# Credential setup - resolve from keychain on Mac Mini
os.environ["OPENCLAW_SECRET_UNITED_USERNAME"] = "marcosathanasoulis"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from openclaw_automation.engine import AutomationEngine

engine = AutomationEngine(ROOT)

print("=" * 60)
print("INTEGRATION TEST: United Award Search via OpenClaw Skill")
print("=" * 60)

# Test via library runner directly (with BrowserAgent)
inputs = {
    "from": "SFO",
    "to": ["NRT"],
    "days_ahead": 14,
    "max_miles": 120000,
    "travelers": 1,
    "cabin": "business",
    "credential_refs": {
        "username": "united/username",
    }
}

print(f"\nInputs: {json.dumps(inputs, indent=2)}")
print("\nRunning United award search (this will use Chrome via CDP)...")
print("CDPLock will be acquired before browser use.\n")

result = engine.run(ROOT / "library" / "united_award", inputs)

print(json.dumps(result, indent=2))

if result["ok"]:
    matches = result.get("result", {}).get("matches", [])
    observations = result.get("result", {}).get("raw_observations", [])
    print(f"\n✓ Search completed: {len(matches)} match(es)")
    for obs in observations:
        print(f"  - {obs}")
else:
    print(f"\n✗ Search failed: {result.get('error', 'unknown')}")

sys.exit(0 if result["ok"] else 1)
