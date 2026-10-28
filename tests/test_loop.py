from desktop_agent.config import Settings
from desktop_agent.core import loop
from desktop_agent.core.loop import run_task
from desktop_agent.core.planner import PlanStep
from desktop_agent.core.verifier import Verdict
from desktop_agent.perception.screen import ScreenShot


def _fake_shot(tmp_path, name="s.png"):
    path = tmp_path / name
    path.write_bytes(b"fake")
    return ScreenShot(
        path=path,
        width=800,
        height=600,
        scale=1.0,
        active_window="test",
        cursor=(0, 0),
    )


def _settings(tmp_path, **overrides):
    return Settings(runs_dir=tmp_path / "runs", **overrides)


def test_loop_stops_at_max_steps(monkeypatch, tmp_path):
    plan = [PlanStep(i, "x", "y", None) for i in range(1, 4)]
    monkeypatch.setattr(loop, "make_plan", lambda *a: plan)
    monkeypatch.setattr(loop, "capture", lambda d: _fake_shot(tmp_path))
    monkeypatch.setattr(
        loop, "operator", lambda step, shot: {"tool": "move", "args": {"x": 1, "y": 1}}
    )
    monkeypatch.setattr(loop, "verify", lambda *a: Verdict("retry", "没成", ""))

    res = run_task(
        "做点事",
        confirm_fn=lambda q: True,
        dry_run=True,
        settings=_settings(tmp_path, max_steps=3),
        use_rag=False,
    )

    assert res.status in {"blocked", "failed"}
    assert res.steps >= 3


def test_destructive_action_not_executed_when_declined(monkeypatch, tmp_path):
    target = tmp_path / "keep.txt"
    target.write_text("重要", encoding="utf-8")

    monkeypatch.setattr(
        loop, "make_plan", lambda *a: [PlanStep(1, "清空文件", "文件为空", "write_file")]
    )
    monkeypatch.setattr(loop, "capture", lambda d: _fake_shot(tmp_path))
    monkeypatch.setattr(
        loop,
        "operator",
        lambda step, shot: {
            "tool": "write_file",
            "args": {"path": str(target), "content": ""},
        },
    )

    res = run_task(
        "清空",
        confirm_fn=lambda q: False,
        dry_run=False,
        settings=_settings(tmp_path),
        use_rag=False,
    )

    assert res.status == "blocked"
    assert target.read_text(encoding="utf-8") == "重要"


def test_verifier_timeout_is_retried_not_fatal(monkeypatch, tmp_path):
    calls = {"n": 0}
    plan = [PlanStep(i, "x", "y", None) for i in range(1, 4)]

    def flaky(*args, **kwargs):
        calls["n"] += 1
        raise TimeoutError("模型超时")

    monkeypatch.setattr(loop, "make_plan", lambda *a: plan)
    monkeypatch.setattr(loop, "capture", lambda d: _fake_shot(tmp_path))
    monkeypatch.setattr(
        loop, "operator", lambda step, shot: {"tool": "move", "args": {"x": 1, "y": 1}}
    )
    monkeypatch.setattr(loop, "verify", flaky)

    res = run_task(
        "做点事",
        confirm_fn=lambda q: True,
        dry_run=True,
        settings=_settings(tmp_path),
        use_rag=False,
    )

    assert calls["n"] >= 2
    assert res.status != "success"


def test_run_task_feeds_retrieved_context_to_planner(monkeypatch, tmp_path):
    seen = {}

    from types import SimpleNamespace

    class FakeSkills:
        def __init__(self, root):
            pass

        def search(self, query, k=3):
            return [SimpleNamespace(task="旧技能", tools=["open_app"])]

    class FakeKnowledge:
        def __init__(self, root):
            pass

        def search(self, query, k=3):
            return [SimpleNamespace(text="住宿不超过 500 元", heading="金额限制")]

    monkeypatch.setattr(loop, "SkillStore", FakeSkills)
    monkeypatch.setattr(loop, "KnowledgeBase", FakeKnowledge)
    monkeypatch.setattr(
        loop,
        "make_plan",
        lambda task, skills, sop: seen.update(skills=skills, sop=sop)
        or [PlanStep(1, "x", "y", None)],
    )
    monkeypatch.setattr(loop, "capture", lambda d: _fake_shot(tmp_path))
    monkeypatch.setattr(
        loop, "operator", lambda step, shot: {"tool": "move", "args": {"x": 1, "y": 1}}
    )
    monkeypatch.setattr(loop, "verify", lambda *a: Verdict("continue", "ok", "截图一致"))

    run_task(
        "做点事",
        confirm_fn=lambda q: True,
        dry_run=True,
        settings=_settings(tmp_path),
    )

    assert seen["skills"][0]["task"] == "旧技能"
    assert seen["sop"][0]["text"] == "住宿不超过 500 元"
