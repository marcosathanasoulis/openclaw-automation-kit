from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


def _repo_root() -> Path:
    env = os.getenv("OPENCLAW_AUTOMATION_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def _run_query(query: str) -> dict:
    root = _repo_root()
    cmd = [
        sys.executable,
        "-m",
        "openclaw_automation.cli",
        "run-query",
        "--query",
        query,
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "run-query failed")
    return json.loads(proc.stdout)


def _assistant_text(result: dict) -> str:
    payload = result.get("result", {}) if isinstance(result, dict) else {}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return "Run completed. Open raw JSON details to inspect parsed fields."


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"ok": False, "error": "Missing query"}), 400

    try:
        result = _run_query(query)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(
        {
            "ok": True,
            "assistant_text": _assistant_text(result),
            "result": result,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
