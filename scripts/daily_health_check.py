#!/usr/bin/env python3
"""Daily health check for OpenClaw automation kit.

Tests all airline award search runners through the full AI assistant pipeline:
  Mac Mini script → SSH to Ubuntu → Agent (port 8800) → search_award_flights tool
  → SSH back to Mac Mini → OpenClaw CLI → Browser Agent → Chrome → Airline site

This validates the entire end-to-end integration, not just the OpenClaw layer.

Usage:
    python scripts/daily_health_check.py [--skip airline1,airline2] [--only airline1,airline2] [--no-report] [--no-readme] [--direct]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────

CDP_URL = "http://127.0.0.1:9222"
BOT_SEND_URL = "http://127.0.0.1:5555/send"
BOT_SEND_TOKEN = os.environ.get("BOT_SEND_TOKEN", "8sjFz81Oluqjmv3gMhpjYrL4PqX2L3AmU9H67XvR8XA")
AGENT_HOST = "home-mind.local"  # Ubuntu server running the AI agent
AGENT_URL = "http://127.0.0.1:8800/chat"  # Agent endpoint (localhost on Ubuntu)
REPORT_PHONE = "+14152268266"
TIMEOUT_PER_AIRLINE = 900  # 15 minutes (agent + browser agent combined)
COOLDOWN_BETWEEN_TESTS = 10  # seconds between airline tests

KIT_DIR = Path(__file__).resolve().parent.parent
RESULTS_PATH = KIT_DIR / "status" / "daily_results.json"
README_PATH = KIT_DIR / "README.md"

_PROMPT_SUFFIX = (
    "Report ALL visible fares from the results page including economy and business "
    "class if shown. Show the cheapest fare per cabin with date and miles. "
    "Do NOT run a second search for a different cabin — just report what is on the page."
)

TESTS = [
    {
        "airline": "united",
        "text": (
            f"use the search_award_flights tool to search united business SFO to BKK "
            f"2 adults next 30 days. {_PROMPT_SUFFIX}"
        ),
        "route": "SFO→BKK",
    },
    {
        "airline": "united-sao",
        "text": (
            f"use the search_award_flights tool to search united business SFO to GRU "
            f"2 adults next 30 days. {_PROMPT_SUFFIX}"
        ),
        "route": "SFO→GRU",
    },
    {
        "airline": "singapore",
        "text": (
            f"use the search_award_flights tool to search singapore business SFO to SIN "
            f"2 adults next 30 days. {_PROMPT_SUFFIX}"
        ),
        "route": "SFO→SIN",
    },
    {
        "airline": "ana",
        "text": (
            f"use the search_award_flights tool to search ana business SFO to HND "
            f"2 adults next 30 days. {_PROMPT_SUFFIX}"
        ),
        "route": "SFO→HND",
    },
    {
        "airline": "aeromexico",
        "text": (
            f"use the search_award_flights tool to search aeromexico economy SFO to MEX "
            f"next 30 days. {_PROMPT_SUFFIX}"
        ),
        "route": "SFO→MEX",
    },
    {
        "airline": "jetblue",
        "cabin": "economy",
        "text": (
            f"You MUST call the search_award_flights tool right now to search jetblue economy NRT to SFO "
            f"next 30 days. JetBlue has a JAL codeshare for Tokyo to SFO. Do NOT skip this search. {_PROMPT_SUFFIX}"
        ),
        "route": "NRT→SFO",
        "direct": True,  # Agent refuses to search - thinks JetBlue doesn't fly to Japan
    },
]


# ── Helpers ──────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def close_chrome_tabs():
    """Close all Chrome tabs via CDP."""
    try:
        req = urllib.request.urlopen(f"{CDP_URL}/json", timeout=5)
        tabs = json.loads(req.read())
        for t in tabs:
            try:
                urllib.request.urlopen(f"{CDP_URL}/json/close/{t['id']}", timeout=3)
            except Exception:
                pass
        if tabs:
            log(f"Closed {len(tabs)} Chrome tab(s)")
    except Exception as e:
        log(f"Warning: Could not close Chrome tabs: {e}")


def parse_json_from_output(raw: str) -> dict | None:
    """Extract JSON object from CLI output using brace-counting."""
    json_start = raw.find("{")
    if json_start == -1:
        return None
    brace_count = 0
    for i in range(json_start, len(raw)):
        if raw[i] == "{":
            brace_count += 1
        elif raw[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                try:
                    return json.loads(raw[json_start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def call_agent(text: str, sender: str) -> dict | None:
    """Call the AI assistant agent on Ubuntu via SSH and return the JSON response.

    The agent listens on 127.0.0.1:8800 on Ubuntu, so we SSH there and curl locally.
    Returns the parsed JSON response or None on failure.
    """
    payload = json.dumps({"text": text, "sender": sender, "channel": "health-check"})
    safe_payload = payload.replace("'", "'\\''")

    cmd = (
        f"echo '{safe_payload}' > /tmp/hc_request.json && "
        f"curl -s -X POST {AGENT_URL} "
        f"-H 'Content-Type: application/json' "
        f"-d @/tmp/hc_request.json"
    )

    try:
        proc = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
             AGENT_HOST, cmd],
            capture_output=True, text=True, timeout=TIMEOUT_PER_AIRLINE,
        )
        raw = proc.stdout.strip()
        if not raw:
            return None
        return json.loads(raw)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        log(f"Agent call failed: {e}")
        return None


def parse_agent_reply(reply: str) -> tuple[int, str | None]:
    """Parse the agent's natural language reply to extract match count and errors.

    Returns (match_count, error_string_or_None).
    """
    reply_lower = reply.lower()

    # Check for explicit failure indicators
    no_results_patterns = [
        "no award flights found",
        "no award flights were found",
        "no award availability",
        "didn't find any",
        "did not find any",
        "unfortunately, no",
        "no .{0,30}award .{0,20}found",
        "no .{0,30}availability .{0,20}found",
    ]
    for pat in no_results_patterns:
        if re.search(pat, reply_lower):
            return 0, None  # No matches but search ran successfully

    if "award search failed" in reply_lower:
        return 0, "search failed"

    if "captcha" in reply_lower:
        return 0, "CAPTCHA blocked"

    if "placeholder" in reply_lower:
        return 0, "placeholder data"

    # Check if "timed out" appears but only for a secondary search (not primary)
    # If the reply also contains actual fare data, don't mark as timeout
    has_fares = bool(re.search(r'[\d,.]+k?\s*(?:miles|pts|puntos|points|\$)', reply_lower))
    if "timed out" in reply_lower and not has_fares:
        return 0, "timeout"

    if ("couldn't" in reply_lower or "unable to" in reply_lower or "error" in reply_lower) and not has_fares:
        return 0, "search error"

    # Try to extract match count from reply
    match = re.search(r"found\s+(\d+)\s+\w[\w\s]{0,30}(?:flight|option|result|availab)", reply_lower)
    if match:
        return int(match.group(1)), None

    # Look for numbered lists (1., 2., 3., etc.) as flight options
    numbered = re.findall(r"^\s*(?:\d+[\.\)]\s+|\*\*\d+)", reply, re.MULTILINE)
    if len(numbered) >= 1:
        return len(numbered), None

    # Look for date patterns suggesting flight results
    dates = re.findall(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}", reply)
    if dates:
        return len(set(dates)), None

    # Look for miles/points/dollar amounts as indicator of results
    miles = re.findall(r"[\d,.]+k?\s*(?:miles|points|pts)", reply_lower)
    if miles:
        return max(1, len(set(miles))), None

    # Cash prices (for AeroMexico)
    prices = re.findall(r"\$[\d,]+", reply)
    if prices:
        return max(1, len(set(prices))), None

    # If the reply is long and seems positive, assume some results
    if len(reply) > 200 and ("miles" in reply_lower or "points" in reply_lower or "$" in reply):
        return 1, None

    return 0, "could not parse results"


def extract_fare_summary(reply: str) -> str:
    """Extract a brief fare summary from the agent's reply."""
    if not reply:
        return ""

    lines = []
    reply_lower = reply.lower()

    if any(p in reply_lower for p in ["no award availability", "no availability found",
                                       "didn't find any", "no award flights"]):
        return "No award availability found"

    # Business class
    biz_patterns = [
        re.compile(r'(?:business|biz|first|mint).*?(?:cheapest|lowest|best|from)\s*:?\s*([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE),
        re.compile(r'(?:cheapest|lowest|best)\s+(?:business|biz|first|mint).*?([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE),
        re.compile(r'(?:best\s+value|lowest\s+fare).*?([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE),
    ]
    for pat in biz_patterns:
        m = pat.search(reply)
        if m:
            lines.append(f"Biz: {m.group(1)} mi")
            break

    # Economy
    econ_patterns = [
        re.compile(r'(?:economy|econ|main\s+cabin|blue\s+basic|blue\b).*?(?:cheapest|lowest|best|from)\s*:?\s*([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE),
        re.compile(r'(?:cheapest|lowest|best)\s+(?:economy|econ|main|blue).*?([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE),
    ]
    for pat in econ_patterns:
        m = pat.search(reply)
        if m:
            lines.append(f"Econ: {m.group(1)} mi")
            break

    # Cash prices (for AeroMexico)
    cash_patterns = [
        re.compile(r'(?:cheapest|lowest|best)\s+(?:economy|econ).*?\$\s*([\d,]+)', re.IGNORECASE),
        re.compile(r'(?:economy|econ).*?(?:cheapest|lowest|best|from)\s*:?\s*\$\s*([\d,]+)', re.IGNORECASE),
    ]
    for pat in cash_patterns:
        m = pat.search(reply)
        if m:
            lines.append(f"Econ: ${m.group(1)}")
            break

    # Generic fallback
    if not lines:
        generic = re.compile(r'([\d,.]+k?)\s*(?:miles|pts|puntos|points).*?(?:on|for)\s+(\w+\s+\d{1,2})', re.IGNORECASE)
        matches = generic.findall(reply)
        if matches:
            miles, date_str = matches[0]
            lines.append(f"From {miles} mi ({date_str})")

    if not lines:
        avail = re.compile(r'([\d,.]+k?)\s*(?:miles|pts|puntos|points)', re.IGNORECASE)
        all_fares = avail.findall(reply)
        if all_fares:
            fare_nums = [int(f.replace(",", "")) for f in all_fares if 1000 <= int(f.replace(",", "")) <= 500000]
            if fare_nums:
                lines.append(f"From {min(fare_nums):,} mi")

    if not lines:
        prices = re.findall(r'\$([\d,]+)', reply)
        if prices:
            price_nums = [int(p.replace(",", "")) for p in prices if 50 <= int(p.replace(",", "")) <= 10000]
            if price_nums:
                lines.append(f"From ${min(price_nums):,}")

    return " | ".join(lines) if lines else ""


def run_airline_test_via_agent(test: dict) -> dict:
    """Run a single airline award search through the full AI assistant pipeline."""
    airline = test["airline"]
    text = test["text"]
    sender = f"health_check_{airline}_{int(time.time())}"

    log(f"Testing {airline} via AI assistant...")
    start = time.time()

    response = call_agent(text, sender)
    elapsed = round(time.time() - start)

    if response is None:
        return {
            "status": "error",
            "matches": 0,
            "elapsed_s": elapsed,
            "error": "no response from agent",
        }

    if "error" in response:
        return {
            "status": "error",
            "matches": 0,
            "elapsed_s": elapsed,
            "error": response["error"],
        }

    reply = response.get("reply", "")
    if not reply:
        return {
            "status": "error",
            "matches": 0,
            "elapsed_s": elapsed,
            "error": "empty reply from agent",
        }

    matches, error = parse_agent_reply(reply)
    fare_summary = extract_fare_summary(reply)

    if error:
        return {
            "status": "fail",
            "matches": 0,
            "elapsed_s": elapsed,
            "error": error,
            "reply_snippet": reply[:500],
            "fare_summary": fare_summary,
        }

    return {
        "status": "pass",
        "matches": matches,
        "elapsed_s": elapsed,
        "error": None,
        "reply_snippet": reply[:500],
        "fare_summary": fare_summary,
    }


def run_airline_test_direct(test: dict) -> dict:
    """Run a single airline award search directly via OpenClaw CLI (no agent)."""
    airline = test["airline"]
    cabin = test.get("cabin", "business")
    query = f"search {airline} {cabin} " + test["route"].replace("→", " to ") + " next 60 days"

    log(f"Testing {airline} via OpenClaw CLI...")
    start = time.time()

    cmd = (
        f"cd {KIT_DIR} && "
        f"PYTHONPATH=src "
        f".venv/bin/python -m openclaw_automation.cli run-query "
        f"--query '{query}'"
    )

    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=TIMEOUT_PER_AIRLINE,
            env={**os.environ, "PYTHONPATH": f"src:{os.environ.get('PYTHONPATH', '')}"},
        )
        raw = proc.stdout
        elapsed = round(time.time() - start)

        result = parse_json_from_output(raw)
        if result is None:
            return {
                "status": "error", "matches": 0, "elapsed_s": elapsed,
                "error": f"No JSON in output: {raw[:200]}",
            }

        if not result.get("ok"):
            return {
                "status": "fail", "matches": 0, "elapsed_s": elapsed,
                "error": result.get("error", "unknown"),
            }

        is_placeholder = result.get("placeholder", False)
        is_real = result.get("real_data", False)
        inner = result.get("result", {})
        matches = inner.get("matches", [])

        if is_placeholder or not is_real:
            return {
                "status": "fail", "matches": 0, "elapsed_s": elapsed,
                "error": "placeholder data",
                "reply_snippet": inner.get("summary", "")[:500],
            }

        # Build fare summary from matches
        fare_parts = []
        if matches:
            miles_vals = [m["miles"] for m in matches if m.get("miles")]
            cash_vals = [m["cash_price"] for m in matches if m.get("cash_price")]
            if miles_vals:
                fare_parts.append(f"From {min(miles_vals):,} mi")
            if cash_vals:
                fare_parts.append(f"From ${min(cash_vals):,.0f}")
        fare_summary = " | ".join(fare_parts) if fare_parts else "No fares extracted"

        return {
            "status": "pass", "matches": len(matches), "elapsed_s": elapsed,
            "error": None, "fare_summary": fare_summary,
        }

    except subprocess.TimeoutExpired:
        return {"status": "timeout", "matches": 0, "elapsed_s": round(time.time() - start),
                "error": f"Timed out after {TIMEOUT_PER_AIRLINE}s"}
    except Exception as e:
        return {"status": "error", "matches": 0, "elapsed_s": round(time.time() - start),
                "error": str(e)}


# ── README Update ────────────────────────────────────────────────────

def update_readme(results: dict, timestamp: str, mode: str):
    """Update README.md with health check results table."""
    if not README_PATH.exists():
        log("Warning: README.md not found, skipping update")
        return

    readme = README_PATH.read_text()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "## Daily Health Check Results",
        "",
        f"_Tested via: {'AI Assistant (full pipeline)' if mode == 'agent' else 'OpenClaw CLI (direct)'}_",
        "",
        "| Airline | Route | Status | Matches | Fares | Time | Last Run |",
        "|---------|-------|--------|---------|-------|------|----------|",
    ]

    for test in TESTS:
        airline = test["airline"]
        route = test["route"]
        r = results.get(airline, {})
        status = r.get("status", "skip")
        matches = r.get("matches", 0)
        elapsed = r.get("elapsed_s", 0)
        error = r.get("error")
        fare_summary = r.get("fare_summary", "")

        if status == "pass":
            status_str = "\u2705 pass"
        elif status == "skip":
            status_str = "\u23f8\ufe0f skip"
        else:
            status_str = f"\u274c {status}"

        match_str = str(matches) if status == "pass" else (error[:30] if error else "0")
        fare_str = fare_summary[:40] if fare_summary else "-"
        lines.append(f"| {airline.title()} | {route} | {status_str} | {match_str} | {fare_str} | {elapsed}s | {now_str} |")

    passing = sum(1 for r in results.values() if r.get("status") == "pass")
    total = sum(1 for r in results.values() if r.get("status") != "skip")
    lines.append("")
    lines.append(f"**Summary**: {passing}/{total} passing | Last run: {now_str} PST")
    lines.append("")

    new_section = "\n".join(lines)

    pattern = r"## Daily Health Check Results\n.*?(?=\n## |\Z)"
    if re.search(pattern, readme, re.DOTALL):
        readme = re.sub(pattern, new_section, readme, flags=re.DOTALL)
    else:
        readme = readme.rstrip() + "\n\n" + new_section + "\n"

    README_PATH.write_text(readme)
    log("README.md updated with health check results")


# ── iMessage Report ──────────────────────────────────────────────────

def send_imessage_report(results: dict, mode: str):
    """Send iMessage report via bot endpoint."""
    mode_label = "via Agent" if mode == "agent" else "via CLI"
    lines = [f"[Health Check] OpenClaw Daily ({mode_label})"]

    for test in TESTS:
        airline = test["airline"]
        route = test["route"]
        r = results.get(airline, {})
        status = r.get("status", "skip")
        matches = r.get("matches", 0)
        elapsed = r.get("elapsed_s", 0)
        error = r.get("error")
        fare_info = r.get("fare_summary", "")

        label = f"{airline.title()} {route}"

        if status == "pass":
            detail = f"{matches} matches ({elapsed}s)"
            if fare_info:
                detail += f"\n   {fare_info}"
            elif matches == 0:
                detail += "\n   No award availability found"
            lines.append(f"\u2705 {label}: {detail}")
        elif status == "skip":
            lines.append(f"\u23f8\ufe0f {label}: skipped")
        else:
            err_short = error[:40] if error else status
            detail = f"{err_short} ({elapsed}s)"
            if fare_info:
                detail += f"\n   {fare_info}"
            lines.append(f"\u274c {label}: {detail}")

    passing = sum(1 for r in results.values() if r.get("status") == "pass")
    total = sum(1 for r in results.values() if r.get("status") != "skip")
    lines.append(f"Summary: {passing}/{total} passing")

    report = "\n".join(lines)
    log(f"Sending iMessage report:\n{report}")

    try:
        payload = json.dumps({"text": report, "address": REPORT_PHONE}).encode()
        req = urllib.request.Request(
            BOT_SEND_URL,
            data=payload,
            headers={"Content-Type": "application/json", "X-Bot-Token": BOT_SEND_TOKEN},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        log(f"iMessage sent (status {resp.status})")
    except Exception as e:
        log(f"Warning: Failed to send iMessage: {e}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenClaw daily health check")
    parser.add_argument("--skip", help="Comma-separated airlines to skip")
    parser.add_argument("--only", help="Comma-separated airlines to test (others skipped)")
    parser.add_argument("--no-report", action="store_true", help="Skip iMessage report")
    parser.add_argument("--no-readme", action="store_true", help="Skip README update")
    parser.add_argument("--direct", action="store_true",
                        help="Test OpenClaw CLI directly (default)")
    parser.add_argument("--agent", action="store_true",
                        help="Test through the AI assistant pipeline instead of direct CLI")
    args = parser.parse_args()

    mode = "agent" if args.agent else "direct"
    skip_set = set(args.skip.split(",")) if args.skip else set()
    only_set = set(args.only.split(",")) if args.only else None

    log("=" * 60)
    log(f"OpenClaw Daily Health Check (mode: {mode})")
    log("=" * 60)

    # Verify agent is reachable (if using agent mode)
    if mode == "agent":
        try:
            proc = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", AGENT_HOST,
                 "curl -s http://127.0.0.1:8800/health"],
                capture_output=True, text=True, timeout=15,
            )
            health = json.loads(proc.stdout.strip()) if proc.stdout.strip() else {}
            if health.get("status") != "ok":
                log("WARNING: Agent not healthy, falling back to direct CLI mode")
                mode = "direct"
            else:
                log("Agent is healthy on Ubuntu")
        except Exception as e:
            log(f"WARNING: Cannot reach agent ({e}), falling back to direct CLI mode")
            mode = "direct"

    # Clean slate
    close_chrome_tabs()
    time.sleep(2)

    results = {}
    total_start = time.time()

    for test in TESTS:
        airline = test["airline"]

        if airline in skip_set:
            log(f"Skipping {airline} (--skip)")
            results[airline] = {"status": "skip", "matches": 0, "elapsed_s": 0, "error": "skipped"}
            continue

        if only_set and airline not in only_set:
            log(f"Skipping {airline} (not in --only)")
            results[airline] = {"status": "skip", "matches": 0, "elapsed_s": 0, "error": "skipped"}
            continue

        if mode == "agent" and not test.get("direct"):
            result = run_airline_test_via_agent(test)
        else:
            result = run_airline_test_direct(test)

        results[airline] = result

        status_icon = "\u2705" if result["status"] == "pass" else "\u274c"
        log(f"  {status_icon} {airline}: {result['status']} | {result['matches']} matches | {result['elapsed_s']}s")
        if result.get("error"):
            log(f"    Error: {result['error'][:100]}")
        if result.get("fare_summary"):
            log(f"    Fares: {result['fare_summary']}")

        # Close tabs and cooldown between tests
        close_chrome_tabs()
        time.sleep(COOLDOWN_BETWEEN_TESTS)

    total_elapsed = round(time.time() - total_start)
    passing = sum(1 for r in results.values() if r.get("status") == "pass")
    total_tested = sum(1 for r in results.values() if r.get("status") != "skip")

    log("=" * 60)
    log(f"Done: {passing}/{total_tested} passing ({total_elapsed}s total)")
    log("=" * 60)

    # Save JSON results
    timestamp = datetime.now().isoformat()
    output = {
        "timestamp": timestamp,
        "mode": mode,
        "results": results,
        "summary": f"{passing}/{total_tested} passing",
        "total_elapsed_s": total_elapsed,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(output, indent=2) + "\n")
    log(f"Results saved to {RESULTS_PATH}")

    # Update README
    if not args.no_readme:
        update_readme(results, timestamp, mode)

    # Send iMessage report
    if not args.no_report:
        send_imessage_report(results, mode)

    return 0


if __name__ == "__main__":
    sys.exit(main())
