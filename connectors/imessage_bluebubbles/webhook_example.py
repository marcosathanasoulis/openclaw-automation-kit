"""Minimal BlueBubbles webhook adapter example.

Receives core automation events and forwards messages to BlueBubbles endpoint.
"""

from __future__ import annotations

import os
import re
import requests


def _normalize_recipient(value: str) -> str:
    """Normalize phone/email/chat-guid target for allowlist comparison."""
    raw = value.strip()
    if ";-;" in raw:
        raw = raw.split(";-;")[-1].strip()
    raw_lower = raw.lower()
    if "@" in raw_lower:
        return raw_lower

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if raw.startswith("+") and re.fullmatch(r"\+\d{8,15}", raw):
        return raw
    return raw


def _allowed_recipients() -> set[str]:
    default_allowlist = "+14152268266,marcos@athanasoulis.net"
    raw = os.environ.get("OPENCLAW_IMESSAGE_ALLOWED_RECIPIENTS", default_allowlist)
    return {_normalize_recipient(v) for v in raw.split(",") if v.strip()}


def send_imessage(phone: str, text: str) -> None:
    normalized_target = _normalize_recipient(phone)
    if normalized_target not in _allowed_recipients():
        raise ValueError(
            "Blocked iMessage send to non-allowlisted recipient: "
            f"{phone!r}. Set OPENCLAW_IMESSAGE_ALLOWED_RECIPIENTS to override."
        )

    webhook = os.environ["BLUEBUBBLES_WEBHOOK_URL"]
    token = os.environ.get("BLUEBUBBLES_TOKEN", "")
    label = os.environ.get("OPENCLAW_IMESSAGE_AGENT_LABEL", "[OpenClaw Parallel]").strip()
    tagged_text = text if not label else f"{label} {text}"
    payload = {"chat_guid": phone, "message": tagged_text}
    headers = {"X-Bot-Token": token} if token else {}
    requests.post(webhook, json=payload, headers=headers, timeout=20).raise_for_status()
