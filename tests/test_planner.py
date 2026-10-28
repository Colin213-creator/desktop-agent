import pytest

from desktop_agent.core import planner
from desktop_agent.core.planner import make_plan


def test_plan_parses_structured_json(monkeypatch):
    monkeypatch.setattr(
        planner,
        "chat",
        lambda *a, **k: {
            "content": '{"steps":[{"intent":"打开记事本","expected":"记事本窗口出现","tool_hint":"open_app"}]}'
        },
    )
    steps = make_plan("打开记事本", [], [])
    assert steps[0].tool_hint == "open_app"
    assert steps[0].expected


def test_plan_rejects_empty(monkeypatch):
    monkeypatch.setattr(planner, "chat", lambda *a, **k: {"content": '{"steps":[]}'})
    with pytest.raises(ValueError):
        make_plan("做点事", [], [])
