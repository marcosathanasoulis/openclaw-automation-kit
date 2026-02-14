from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_demo_module():
    app_path = Path(__file__).resolve().parents[1] / "demo" / "chat-demo" / "app.py"
    spec = importlib.util.spec_from_file_location("demo_chat_app", app_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_headlines_demo_route(monkeypatch) -> None:
    mod = _load_demo_module()

    def fake_run_script(script_dir: str, inputs: dict) -> dict:
        assert script_dir == "library/site_headlines"
        assert inputs["url"] == "https://www.yahoo.com"
        return {"ok": True, "result": {"summary": "headlines demo ok"}}

    monkeypatch.setattr(mod, "_run_script", fake_run_script)
    client = mod.app.test_client()
    resp = client.post("/api/chat", json={"query": "Run headlines demo"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["assistant_text"] == "headlines demo ok"


def test_text_watch_demo_route(monkeypatch) -> None:
    mod = _load_demo_module()

    def fake_run_script(script_dir: str, inputs: dict) -> dict:
        assert script_dir == "library/site_text_watch"
        assert "status" in [x.lower() for x in inputs["must_include"]]
        return {"ok": True, "result": {"summary": "text watch demo ok"}}

    monkeypatch.setattr(mod, "_run_script", fake_run_script)
    client = mod.app.test_client()
    resp = client.post("/api/chat", json={"query": "Run text watch demo"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["assistant_text"] == "text watch demo ok"
