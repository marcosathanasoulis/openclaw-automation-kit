#!/usr/bin/env python3
"""
Daily Award Scan — runs configured award searches via kit runners.

Lives in the openclaw-automation-kit repo at scripts/daily_award_scan.py.
Uses the kit's runners (library/*/runner.py) to search each airline.

Usage:
    cd ~/openclaw-automation-kit
    set -a && source .env && set +a
    python scripts/daily_award_scan.py --send-report [--only delta,sia] [--skip united]

Environment:
    OPENCLAW_USE_BROWSER_AGENT=true
    OPENCLAW_BROWSER_AGENT_PATH=~/athanasoulis-ai-assistant/src/browser
    OPENCLAW_CDP_URL=http://127.0.0.1:9222
    ANTHROPIC_API_KEY=...
    AUTOMATION_KEYCHAIN_PASSWORD=...
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure kit is importable
_kit_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_kit_root / "src"))

log = logging.getLogger("daily_scan")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/daily_award_scan.log"),
    ],
)

IMESSAGE_URL = "http://127.0.0.1:5555/send"
IMESSAGE_TOKEN = "8sjFz81Oluqjmv3gMhpjYrL4PqX2L3AmU9H67XvR8XA"
MY_PHONE = "+14152268266"

# ── Search schedule ──────────────────────────────────────────────────────────
# Target month — update this when you want to scan a different month
TARGET_MONTH_NAME = "June"
TARGET_YEAR = 2026

def _days_to_mid_month():
    """Calculate days_ahead to target the 15th of the target month."""
    target = date(TARGET_YEAR, 6, 15)  # June 15
    delta = (target - date.today()).days
    return max(1, delta)

# Each search maps to a kit runner via script_dir
# Order: United LAST (to allow cooldown)
SEARCHES: List[Dict[str, Any]] = [
    {
        "airline": "ana",
        "name": "ANA",
        "script_dir": "library/ana_award",
        "inputs": {
            "from": "SFO",
            "to": ["NRT"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
    {
        "airline": "sia",
        "name": "Singapore Airlines",
        "script_dir": "library/singapore_award",
        "inputs": {
            "from": "SFO",
            "to": ["SIN"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
    {
        "airline": "jetblue",
        "name": "JetBlue",
        "script_dir": "library/jetblue_award",
        "inputs": {
            "from": "SFO",
            "to": ["NRT"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
    {
        "airline": "aeromexico",
        "name": "AeroMexico",
        "script_dir": "library/aeromexico_award",
        "inputs": {
            "from": "SFO",
            "to": ["CUN"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
    {
        "airline": "delta",
        "name": "Delta",
        "script_dir": "library/delta_award",
        "inputs": {
            "from": "SFO",
            "to": ["BOS"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
    {
        "airline": "united",
        "name": "United",
        "script_dir": "library/united_award",
        "inputs": {
            "from": "SFO",
            "to": ["SIN"],
            "travelers": 2,
            "cabin": "economy",
            "max_miles": 999999,
        },
    },
]

# Cooldowns (seconds)
COOLDOWN_NORMAL = 120
COOLDOWN_RATE_LIMITED = 600


# ── Runner execution ─────────────────────────────────────────────────────────

def run_one(script_dir: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Import and run a kit runner directly."""
    runner_path = _kit_root / script_dir / "runner.py"
    if not runner_path.exists():
        return {"mode": "error", "matches": [], "summary": f"Runner not found: {runner_path}",
                "errors": [f"Missing {runner_path}"]}

    # Dynamic import
    spec = importlib.util.spec_from_file_location("runner", str(runner_path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        return {"mode": "error", "matches": [], "summary": f"Import error: {e}",
                "errors": [str(e)]}

    context = {"unresolved_credential_refs": []}

    try:
        result = module.run(context, inputs)
        return result
    except Exception as e:
        return {"mode": "error", "matches": [], "summary": f"Runner error: {e}",
                "errors": [str(e)]}


def detect_rate_limit(result: Dict[str, Any]) -> bool:
    """Check if result suggests rate limiting."""
    text = json.dumps(result).lower()
    indicators = ["unable to complete", "try again later", "rate limit",
                   "captcha", "blocked", "access denied"]
    return any(ind in text for ind in indicators)


# ── Report compilation ───────────────────────────────────────────────────────

def format_matches(matches: List[Dict], max_show=15) -> str:
    """Format match list into readable string."""
    if not matches:
        return "No availability found"
    lines = []
    for m in matches[:max_show]:
        d = m.get("date", "?")
        miles = m.get("miles", 0)
        cabin = m.get("cabin", "?")
        notes = m.get("notes", "")
        if miles:
            lines.append(f"  {d}: {miles:,} miles ({cabin})")
        elif notes:
            lines.append(f"  {d}: {notes[:80]}")
    if len(matches) > max_show:
        lines.append(f"  ... and {len(matches) - max_show} more")
    return "\n".join(lines)


def compile_report(all_results: Dict[str, Dict]) -> str:
    """Build the final iMessage report."""
    lines = []
    lines.append(f"✈️ Daily Award Scan — {TARGET_MONTH_NAME} {TARGET_YEAR}")
    lines.append(f"SFO | 2 pax | {datetime.now().strftime('%b %d %H:%M')}")
    lines.append("")

    for search in SEARCHES:
        airline = search["airline"]
        name = search["name"]
        dest = search["inputs"]["to"][0]
        result = all_results.get(airline)

        lines.append(f"{'─'*35}")
        lines.append(f"{name} — SFO → {dest}")

        if not result:
            lines.append("  ⏭ Skipped")
            lines.append("")
            continue

        mode = result.get("mode", "unknown")
        matches = result.get("matches", [])
        summary = result.get("summary", "")
        errors = result.get("errors", [])
        real_data = result.get("real_data", False)

        if mode == "error" or errors:
            err_msg = errors[0][:120] if errors else "Unknown error"
            lines.append(f"  ❌ {err_msg}")
        elif not real_data and mode == "placeholder":
            lines.append("  ⚠️ Placeholder data (browser agent not enabled?)")
        elif matches:
            # Group by cabin
            econ = [m for m in matches if m.get("cabin", "").lower() in ("economy", "coach", "main", "blue", "")]
            biz = [m for m in matches if m.get("cabin", "").lower() in ("business", "first", "delta_one", "polaris", "mint", "premier")]

            if econ:
                best_e = min(m["miles"] for m in econ if m.get("miles"))
                lines.append(f"  Economy: {len(econ)} options, best {best_e:,} miles")
            if biz:
                best_b = min(m["miles"] for m in biz if m.get("miles"))
                lines.append(f"  Business: {len(biz)} options, best {best_b:,} miles")
            if not econ and not biz:
                lines.append(f"  {len(matches)} results found")
                for m in matches[:5]:
                    lines.append(f"    {m.get('date','?')}: {m.get('miles',0):,} miles")
        elif summary:
            lines.append(f"  {summary[:200]}")
        else:
            lines.append("  No results")

        lines.append("")

    lines.append("─" * 35)
    lines.append("End of daily scan.")
    return "\n".join(lines)


def send_imessage(text: str):
    """Send via iMessage bot, truncate if needed."""
    if len(text) > 3000:
        text = text[:2900] + "\n\n... (truncated)"
    try:
        import requests
        resp = requests.post(
            IMESSAGE_URL,
            json={"text": text, "address": MY_PHONE, "chat_guid": f"iMessage;-;{MY_PHONE}"},
            timeout=15,
        )
        log.info("iMessage sent: %s", resp.status_code)
    except Exception as e:
        log.warning("iMessage failed: %s", e)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Daily Award Scan")
    parser.add_argument("--send-report", action="store_true")
    parser.add_argument("--only", help="Only these airlines (comma-sep)")
    parser.add_argument("--skip", help="Skip these airlines (comma-sep)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    searches = SEARCHES[:]
    if args.only:
        only = set(args.only.lower().split(","))
        searches = [s for s in searches if s["airline"] in only]
    if args.skip:
        skip = set(args.skip.lower().split(","))
        searches = [s for s in searches if s["airline"] not in skip]

    log.info("Daily Award Scan — %s %s", TARGET_MONTH_NAME, TARGET_YEAR)
    log.info("Airlines: %s", ", ".join(s["name"] for s in searches))
    log.info("Kit root: %s", _kit_root)

    if args.dry_run:
        for s in searches:
            log.info("  Would run: %s SFO → %s", s["name"], s["inputs"]["to"][0])
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    days_ahead = _days_to_mid_month()
    log.info("Days ahead to mid-%s: %d", TARGET_MONTH_NAME, days_ahead)

    all_results = {}

    for i, search in enumerate(searches):
        airline = search["airline"]
        name = search["name"]
        script_dir = search["script_dir"]
        inputs = dict(search["inputs"])
        inputs["days_ahead"] = days_ahead

        log.info("Running %s: SFO → %s ...", name, inputs["to"][0])
        start_t = time.time()

        result = run_one(script_dir, inputs)
        elapsed = time.time() - start_t

        matches = result.get("matches", [])
        mode = result.get("mode", "?")
        real = result.get("real_data", False)
        errors = result.get("errors", [])

        log.info("  %s done in %.0fs: mode=%s real=%s matches=%d errors=%d",
                 name, elapsed, mode, real, len(matches), len(errors))

        all_results[airline] = result

        # Rate limit detection & cooldown
        rate_limited = detect_rate_limit(result)
        if rate_limited:
            log.warning("  %s may be rate limited, cooling down %ds", name, COOLDOWN_RATE_LIMITED)
            if i < len(searches) - 1:
                time.sleep(COOLDOWN_RATE_LIMITED)
        elif i < len(searches) - 1:
            log.info("  Cooling down %ds...", COOLDOWN_NORMAL)
            time.sleep(COOLDOWN_NORMAL)

    report = compile_report(all_results)
    print("\n" + report)

    if args.send_report:
        send_imessage(report)

    log.info("Daily scan complete.")


if __name__ == "__main__":
    main()
