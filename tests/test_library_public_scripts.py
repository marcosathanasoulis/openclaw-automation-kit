import importlib.util
from pathlib import Path


def _load_runner(path: str):
    runner_path = Path(__file__).resolve().parents[1] / path
    spec = importlib.util.spec_from_file_location(f"runner_{runner_path.stem}", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


headlines_runner = _load_runner("library/site_headlines/runner.py")
text_watch_runner = _load_runner("library/site_text_watch/runner.py")


def test_site_headlines_extracts_headings(monkeypatch) -> None:
    sample_html = """
    <html><head><title>Example Home</title></head>
    <body><h1>Top Story</h1><h2>Second Story</h2></body></html>
    """
    monkeypatch.setattr(headlines_runner, "_fetch_html", lambda _url: sample_html)
    out = headlines_runner.run({}, {"url": "https://example.com", "max_items": 5})
    assert out["title"] == "Example Home"
    assert "Top Story" in out["headlines"]
    assert out["errors"] == []


def test_site_text_watch_required_and_forbidden(monkeypatch) -> None:
    sample_text = "Service Status: all systems operational. No outage right now."
    monkeypatch.setattr(text_watch_runner, "_fetch_text", lambda _url: sample_text)
    out = text_watch_runner.run(
        {},
        {
            "url": "https://status.example.com",
            "must_include": ["Status", "operational"],
            "must_not_include": ["maintenance"],
            "case_sensitive": False,
        },
    )
    assert out["all_required_present"] is True
    assert out["missing_required"] == []
    assert out["forbidden_found"] == []
