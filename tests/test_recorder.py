from desktop_agent.memory import recorder
from desktop_agent.memory.recorder import events_to_skill, replay_events


def test_events_become_skill_with_tool_sequence():
    events = [
        {"type": "key", "key": "ctrl+n"},
        {"type": "text", "text": "你好"},
        {"type": "key", "key": "ctrl+s"},
    ]

    skill = events_to_skill(events)

    assert skill.tools == ["press_keys", "type_text", "press_keys"]


def test_replay_dry_run_does_not_touch_desktop(monkeypatch):
    called = []
    monkeypatch.setattr(recorder, "execute", lambda name, args: called.append(name) or {})

    replay_events([{"type": "text", "text": "x"}], dry_run=True)

    assert called == []
