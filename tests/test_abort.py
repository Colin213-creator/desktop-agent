import pytest

from desktop_agent.actions import registry
from desktop_agent.config import Settings
from desktop_agent.core import loop
from desktop_agent.core.loop import run_task
from desktop_agent.core.planner import PlanStep
from desktop_agent.perception.screen import ScreenShot
from desktop_agent.safety.abort import AgentAborted


def test_execute_propagates_abort_signal(monkeypatch):
    def boom(x, y):
        raise AgentAborted()

    monkeypatch.setitem(registry._IMPL, "move", boom)

    with pytest.raises(AgentAborted):
        registry.execute("move", {"x": 1, "y": 1})


def test_run_task_reports_aborted(monkeypatch, tmp_path):
    shot = tmp_path / "s.png"
    shot.write_bytes(b"fake")

    monkeypatch.setattr(loop, "make_plan", lambda *a: [PlanStep(1, "x", "y", None)])
    monkeypatch.setattr(
        loop,
        "capture",
        lambda d: ScreenShot(shot, 800, 600, 1.0, "test", (0, 0)),
    )

    def stop(step, screen):
        raise AgentAborted()

    monkeypatch.setattr(loop, "operator", stop)

    result = run_task(
        "做点事",
        confirm_fn=lambda q: True,
        dry_run=True,
        settings=Settings(runs_dir=tmp_path / "runs"),
        use_rag=False,
    )

    assert result.status == "aborted"
