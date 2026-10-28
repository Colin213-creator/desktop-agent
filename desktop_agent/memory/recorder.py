"""示范学习：录制人手的键鼠操作，抽象成可复用的技能。

录下来的是原始事件，不能直接当脚本回放——必须先抽象成"工具序列"，
否则换个窗口、换个文件就全废了。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..actions.registry import execute
from .skills import Skill


def record_session(seconds: int, out: Path) -> Path:
    """录制一段键鼠操作，按 ESC 可提前结束。"""
    from pynput import keyboard

    events: list[dict] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            events.append({"type": "text", "text": "".join(buffer)})
            buffer.clear()

    def on_press(key) -> bool | None:
        if key == keyboard.Key.esc:
            return False
        char = getattr(key, "char", None)
        if char:
            buffer.append(char)
        else:
            flush()
            name = str(key).split(".")[-1]
            events.append({"type": "key", "key": name})
        return None

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    deadline = time.monotonic() + max(1, int(seconds))
    while listener.running and time.monotonic() < deadline:
        time.sleep(0.2)
    listener.stop()
    flush()

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def events_to_skill(events: list[dict], task: str = "人手示范的操作") -> Skill:
    """把原始事件映射成工具名序列。"""
    mapping = {"key": "press_keys", "text": "type_text", "click": "click", "move": "move"}
    tools = [mapping[e["type"]] for e in events if e.get("type") in mapping]
    return Skill(
        id="",
        task=task,
        precondition="由人手录制",
        tools=tools,
        success_count=0,
        avg_steps=len(tools),
        vector=[],
    )


def replay_events(events: list[dict], dry_run: bool = True) -> list[dict]:
    """把事件翻译成工具调用。dry_run=True 时只返回计划，不碰桌面。"""
    actions: list[dict] = []
    for event in events:
        kind = event.get("type")
        if kind == "key":
            actions.append(
                {"tool": "press_keys", "args": {"keys": str(event["key"]).split("+")}}
            )
        elif kind == "text":
            actions.append({"tool": "type_text", "args": {"text": event["text"]}})
        elif kind == "click":
            actions.append(
                {"tool": "click", "args": {"x": event["x"], "y": event["y"]}}
            )
        elif kind == "move":
            actions.append(
                {"tool": "move", "args": {"x": event["x"], "y": event["y"]}}
            )

    if dry_run:
        return actions

    for action in actions:
        execute(action["tool"], action["args"])
    return actions
