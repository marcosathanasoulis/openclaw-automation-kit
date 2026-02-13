"""Minimal BlueBubbles webhook adapter example.

Receives core automation events and forwards messages to BlueBubbles endpoint.
"""

from __future__ import annotations

import os
import requests


def send_imessage(phone: str, text: str) -> None:
    webhook = os.environ["BLUEBUBBLES_WEBHOOK_URL"]
    token = os.environ.get("BLUEBUBBLES_TOKEN", "")
    payload = {"chat_guid": phone, "message": text}
    headers = {"X-Bot-Token": token} if token else {}
    requests.post(webhook, json=payload, headers=headers, timeout=20).raise_for_status()
