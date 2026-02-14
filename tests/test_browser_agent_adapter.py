import types
import sys
from pathlib import Path

from openclaw_automation.browser_agent_adapter import run_browser_agent_goal
from openclaw_automation.engine import AutomationEngine


class _FakeBrowserAgent:
    last_kwargs = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeBrowserAgent.last_kwargs = kwargs

    def run(self):
        return {
            "status": "success",
            "steps": 5,
            "trace_dir": "browser_runs/fake",
            "matches": [{"route": "SFO-AMS", "miles": 80000}],
        }


def test_adapter_imports_fake_module(monkeypatch):
    fake_module = types.SimpleNamespace(BrowserAgent=_FakeBrowserAgent)
    monkeypatch.setenv("OPENCLAW_BROWSER_AGENT_MODULE", "fake_browser_agent")
    monkeypatch.setitem(sys.modules, "fake_browser_agent", fake_module)
    result = run_browser_agent_goal(
        goal="test goal",
        url="https://example.com",
        max_steps=3,
        trace=False,
        use_vision=False,
    )
    assert result["ok"] is True
    assert result["result"]["status"] == "success"


def test_united_runner_uses_browser_agent_when_enabled(monkeypatch):
    fake_module = types.SimpleNamespace(BrowserAgent=_FakeBrowserAgent)
    monkeypatch.setenv("OPENCLAW_USE_BROWSER_AGENT", "true")
    monkeypatch.setenv("OPENCLAW_BROWSER_AGENT_MODULE", "fake_browser_agent")
    monkeypatch.setitem(sys.modules, "fake_browser_agent", fake_module)

    root = Path(__file__).resolve().parents[1]
    engine = AutomationEngine(root)
    result = engine.run(
        root / "library" / "united_award",
        {
            "from": "SFO",
            "to": ["AMS"],
            "days_ahead": 30,
            "max_miles": 120000,
            "travelers": 2,
            "cabin": "business",
        },
    )
    assert result["ok"] is True
    assert result["result"]["matches"]


def test_adapter_allows_env_to_disable_trace(monkeypatch):
    fake_module = types.SimpleNamespace(BrowserAgent=_FakeBrowserAgent)
    monkeypatch.setenv("OPENCLAW_BROWSER_AGENT_MODULE", "fake_browser_agent")
    monkeypatch.setenv("OPENCLAW_BROWSER_TRACE", "false")
    monkeypatch.setitem(sys.modules, "fake_browser_agent", fake_module)
    run_browser_agent_goal(
        goal="test goal",
        url="https://example.com",
        max_steps=3,
        trace=True,
        use_vision=False,
    )
    assert _FakeBrowserAgent.last_kwargs is not None
    assert _FakeBrowserAgent.last_kwargs["trace"] is False
