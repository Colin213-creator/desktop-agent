from desktop_agent import llm
from desktop_agent.llm import health


def test_health_reports_model_and_capabilities():
    h = health()
    assert h["ok"] is True
    assert "tools" in h["capabilities"] and "vision" in h["capabilities"]


def test_health_returns_error_instead_of_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(llm.requests, "post", boom)
    h = health()
    assert h["ok"] is False and "boom" in h["error"]
