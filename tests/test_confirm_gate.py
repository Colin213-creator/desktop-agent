from desktop_agent.actions.registry import execute
from desktop_agent.safety.guard import guarded_execute, require_confirm


def test_destructive_tool_blocked_before_action(tmp_path):
    target = tmp_path / "keep.txt"
    target.write_text("重要", encoding="utf-8")
    asked = []

    ok = require_confirm(
        "write_file",
        {"path": str(target), "content": ""},
        confirm_fn=lambda q: (asked.append(q), False)[1],
    )

    assert ok is False
    assert asked
    assert target.read_text(encoding="utf-8") == "重要"


def test_guarded_execute_does_not_write_when_declined(tmp_path):
    target = tmp_path / "keep.txt"
    target.write_text("重要", encoding="utf-8")

    result = guarded_execute(
        "write_file",
        {"path": str(target), "content": "覆盖"},
        confirm_fn=lambda q: False,
        execute_fn=execute,
    )

    assert result.get("blocked") is True
    assert target.read_text(encoding="utf-8") == "重要"


def test_guarded_execute_writes_after_confirmation(tmp_path):
    target = tmp_path / "ok.txt"
    result = guarded_execute(
        "write_file",
        {"path": str(target), "content": "新内容"},
        confirm_fn=lambda q: True,
        execute_fn=execute,
    )

    assert result.get("ok") is True
    assert target.read_text(encoding="utf-8") == "新内容"
