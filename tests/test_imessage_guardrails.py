from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    mod_path = (
        Path(__file__).resolve().parents[1]
        / "connectors"
        / "imessage_bluebubbles"
        / "webhook_example.py"
    )
    spec = importlib.util.spec_from_file_location("webhook_example", mod_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bb = _load_module()


class _DummyResponse:
    def raise_for_status(self) -> None:
        return None


def test_send_imessage_blocks_non_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBUBBLES_WEBHOOK_URL", "http://127.0.0.1:5555/send")
    monkeypatch.setenv("OPENCLAW_IMESSAGE_ALLOWED_RECIPIENTS", "+14152268266")

    with pytest.raises(ValueError):
        bb.send_imessage("+14155550123", "hello")


def test_send_imessage_tags_and_sends_for_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUEBUBBLES_WEBHOOK_URL", "http://127.0.0.1:5555/send")
    monkeypatch.setenv("BLUEBUBBLES_TOKEN", "token-123")
    monkeypatch.setenv("OPENCLAW_IMESSAGE_ALLOWED_RECIPIENTS", "+14152268266,marcos@athanasoulis.net")
    monkeypatch.setenv("OPENCLAW_IMESSAGE_AGENT_LABEL", "[OpenClaw Test]")

    captured: dict = {}

    def _fake_post(url: str, json: dict, headers: dict, timeout: int) -> _DummyResponse:  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _DummyResponse()

    monkeypatch.setattr(bb.requests, "post", _fake_post)

    # 10-digit phone should normalize to +1... for allowlist match.
    bb.send_imessage("415-226-8266", "hello")

    assert captured["url"] == "http://127.0.0.1:5555/send"
    assert captured["json"]["chat_guid"] == "415-226-8266"
    assert captured["json"]["message"] == "[OpenClaw Test] hello"
    assert captured["headers"]["X-Bot-Token"] == "token-123"
    assert captured["timeout"] == 20
