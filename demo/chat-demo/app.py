from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
CHALLENGE_DIR = Path("/tmp/openclaw-demo-challenges")
CHALLENGES: dict[str, dict] = {}
TWOFA_FLOWS: dict[str, dict] = {}


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


def _run_script(script_dir: str, inputs: dict) -> dict:
    root = _repo_root()
    cmd = [
        sys.executable,
        "-m",
        "openclaw_automation.cli",
        "run",
        "--script-dir",
        script_dir,
        "--input",
        json.dumps(inputs),
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "run failed")
    return json.loads(proc.stdout)


def _assistant_text(result: dict) -> str:
    payload = result.get("result", {}) if isinstance(result, dict) else {}
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return "Run completed. Open raw JSON details to inspect parsed fields."


def _new_challenge() -> dict:
    CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
    challenge_id = uuid.uuid4().hex[:10]
    target = sorted(random.sample(range(1, 13), 3))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    img = Image.new("RGB", (560, 440), color=(16, 24, 39))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((20, 14), "Mock CAPTCHA Challenge", fill=(255, 255, 255), font=font)
    draw.text((20, 32), "Pick the green tiles and reply with their numbers.", fill=(200, 215, 240), font=font)

    tile_w, tile_h = 120, 88
    gap_x, gap_y = 12, 12
    start_x, start_y = 20, 62
    for idx in range(1, 13):
        row = (idx - 1) // 4
        col = (idx - 1) % 4
        x = start_x + col * (tile_w + gap_x)
        y = start_y + row * (tile_h + gap_y)
        is_target = idx in target
        bg = (34, 197, 94) if is_target else (31, 41, 55)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=10, fill=bg, outline=(148, 163, 184), width=2)
        draw.text((x + 56, y + 36), str(idx), fill=(255, 255, 255), font=font)

    image_path = CHALLENGE_DIR / f"{challenge_id}.png"
    img.save(image_path)
    CHALLENGES[challenge_id] = {
        "target": target,
        "expires_at": expires_at,
    }
    return {
        "challenge_id": challenge_id,
        "target": target,
        "image_path": image_path,
        "expires_at": expires_at.isoformat(),
    }


def _solve_challenge(challenge_id: str, solution: str) -> dict:
    record = CHALLENGES.get(challenge_id)
    if not record:
        return {"ok": False, "error": "Unknown challenge_id"}
    if datetime.now(timezone.utc) > record["expires_at"]:
        return {"ok": False, "error": "Challenge expired"}
    parsed = sorted(
        int(s.strip()) for s in solution.split(",") if s.strip().isdigit()
    )
    if parsed == record["target"]:
        CHALLENGES.pop(challenge_id, None)
        return {"ok": True, "status": "passed"}
    return {"ok": False, "error": "Incorrect solution"}


def _new_twofa_flow() -> dict:
    flow_id = uuid.uuid4().hex[:10]
    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    TWOFA_FLOWS[flow_id] = {"code": code, "expires_at": expires_at}
    return {
        "flow_id": flow_id,
        "expires_at": expires_at.isoformat(),
    }


def _verify_twofa(flow_id: str, code: str) -> dict:
    flow = TWOFA_FLOWS.get(flow_id)
    if not flow:
        return {"ok": False, "error": "Unknown flow_id"}
    if datetime.now(timezone.utc) > flow["expires_at"]:
        return {"ok": False, "error": "Code expired"}
    if code.strip() != flow["code"]:
        return {"ok": False, "error": "Invalid code"}
    TWOFA_FLOWS.pop(flow_id, None)
    return {"ok": True, "status": "passed"}


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/demo/challenge/<challenge_id>.png")
def challenge_image(challenge_id: str):
    path = CHALLENGE_DIR / f"{challenge_id}.png"
    if not path.exists():
        return jsonify({"ok": False, "error": "Not found"}), 404
    return send_file(path, mimetype="image/png")


@app.get("/demo/2fa/<flow_id>")
def twofa_inbox(flow_id: str):
    flow = TWOFA_FLOWS.get(flow_id)
    if not flow:
        return jsonify({"ok": False, "error": "Unknown flow_id"}), 404
    if datetime.now(timezone.utc) > flow["expires_at"]:
        return jsonify({"ok": False, "error": "Code expired"}), 410
    return jsonify(
        {
            "ok": True,
            "flow_id": flow_id,
            "message": f"Your one-time code is {flow['code']}",
            "expires_at": flow["expires_at"].isoformat(),
        }
    )


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return jsonify({"ok": False, "error": "Missing query"}), 400

    lower = query.lower()

    if "captcha demo" in lower or "challenge demo" in lower:
        challenge = _new_challenge()
        challenge_id = challenge["challenge_id"]
        return jsonify(
            {
                "ok": True,
                "assistant_text": (
                    "Challenge detected. I captured a screenshot for you. "
                    f"Reply: solve {challenge_id} n,n,n"
                ),
                "challenge_id": challenge_id,
                "challenge_image_url": f"/demo/challenge/{challenge_id}.png",
                "expires_at": challenge["expires_at"],
                "result": {"mode": "human_loop_demo", "step": "challenge_required"},
            }
        )

    if "2fa demo" in lower or "two factor demo" in lower or "otp demo" in lower:
        flow = _new_twofa_flow()
        flow_id = flow["flow_id"]
        return jsonify(
            {
                "ok": True,
                "assistant_text": (
                    "Two-factor challenge created. Simulated code sent to demo inbox. "
                    f"Open /demo/2fa/{flow_id} to read it, then reply: otp {flow_id} XXXXXX"
                ),
                "twofa_flow_id": flow_id,
                "twofa_inbox_url": f"/demo/2fa/{flow_id}",
                "expires_at": flow["expires_at"],
                "result": {"mode": "human_loop_demo", "step": "twofa_required"},
            }
        )

    if lower.startswith("otp "):
        parts = query.split(maxsplit=2)
        if len(parts) < 3:
            return jsonify({"ok": False, "error": "Format: otp <flow_id> <6-digit-code>"}), 400
        verdict = _verify_twofa(parts[1], parts[2])
        if verdict["ok"]:
            return jsonify(
                {
                    "ok": True,
                    "assistant_text": "2FA code accepted. Run resumed successfully.",
                    "result": {"mode": "human_loop_demo", "step": "resumed", "status": "success"},
                }
            )
        return jsonify({"ok": False, "error": verdict["error"]}), 400

    if "headlines demo" in lower:
        result = _run_script("library/site_headlines", {"url": "https://www.yahoo.com", "max_items": 8})
        payload = result.get("result", {})
        return jsonify(
            {
                "ok": True,
                "assistant_text": payload.get("summary", "Headlines demo completed."),
                "result": result,
            }
        )

    if "text watch demo" in lower or "website watch demo" in lower:
        result = _run_script(
            "library/site_text_watch",
            {
                "url": "https://status.openai.com",
                "must_include": ["status"],
                "must_not_include": ["maintenance window"],
                "case_sensitive": False,
            },
        )
        payload = result.get("result", {})
        return jsonify(
            {
                "ok": True,
                "assistant_text": payload.get("summary", "Text watch demo completed."),
                "result": result,
            }
        )

    if lower.startswith("solve "):
        parts = query.split(maxsplit=2)
        if len(parts) < 3:
            return jsonify({"ok": False, "error": "Format: solve <challenge_id> <n,n,n>"}), 400
        verdict = _solve_challenge(parts[1], parts[2])
        if verdict["ok"]:
            return jsonify(
                {
                    "ok": True,
                    "assistant_text": "Challenge solved. Run resumed successfully.",
                    "result": {"mode": "human_loop_demo", "step": "resumed", "status": "success"},
                }
            )
        return jsonify({"ok": False, "error": verdict["error"]}), 400

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
