import importlib.util
from pathlib import Path


def _load_runner(path: str):
    runner_path = Path(__file__).resolve().parents[1] / path
    spec = importlib.util.spec_from_file_location(f"runner_{runner_path.stem}", runner_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


search_runner = _load_runner("library/web_search_brief/runner.py")


def test_web_search_brief_extracts_results_and_prices(monkeypatch) -> None:
    sample_html = """
    <html><body>
      <a class="result__a" href="https://html.duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fhotel-a">
        Hotel A in Manhattan
      </a>
      <div class="result__snippet">One-bedroom suite from US$429 per night</div>
      <a class="result__a" href="https://example.com/hotel-b">Hotel B</a>
      <a class="result__snippet" href="https://example.com/hotel-b">Rates start at $389 and include breakfast</a>
    </body></html>
    """
    monkeypatch.setattr(search_runner, "_fetch_html", lambda _url: sample_html)
    out = search_runner.run({}, {"query": "manhattan hotel suite", "max_results": 5, "kind": "hotel"})
    assert out["errors"] == []
    assert len(out["results"]) == 2
    assert out["results"][0]["url"] == "https://example.com/hotel-a"
    assert out["best_price_hint"]["value"] == 389.0
    assert "Lowest visible price hint" in out["summary"]


def test_web_search_brief_handles_fetch_errors(monkeypatch) -> None:
    def _boom(_url: str) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(search_runner, "_fetch_html", _boom)
    out = search_runner.run({}, {"query": "french restaurant marin"})
    assert out["results"] == []
    assert out["best_price_hint"] is None
    assert out["errors"]
