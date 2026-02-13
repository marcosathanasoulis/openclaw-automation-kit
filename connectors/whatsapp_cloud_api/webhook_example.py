"""Minimal WhatsApp Cloud API adapter example."""

from __future__ import annotations

import os
import requests


def send_whatsapp(to_phone: str, text: str) -> None:
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    token = os.environ["WHATSAPP_ACCESS_TOKEN"]
    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(url, json=payload, headers=headers, timeout=20).raise_for_status()
