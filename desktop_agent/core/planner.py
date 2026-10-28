"""任务规划：把自然语言任务拆成带预期结果的步骤。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..llm import chat
from ..orchestration.roles import PLANNER_PROMPT

MAX_STEPS = 15


@dataclass(frozen=True)
class PlanStep:
    id: int
    intent: str
    expected: str
    tool_hint: str | None


def _extract_json(text: str) -> dict:
    """模型可能包一层 markdown 代码块，这里剥掉再取第一个 JSON 对象。"""
    raw = (text or "").strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型没有返回 JSON")
    return json.loads(raw[start : end + 1])


def _build_messages(task: str, skills: list[dict], sop: list[dict]) -> list[dict]:
    sections = [f"任务：{task}"]
    if skills:
        brief = "；".join(str(s.get("task", "")) for s in skills[:3])
        sections.append(f"可参考的历史技能：{brief}")
    if sop:
        brief = "\n".join(str(c.get("text", ""))[:300] for c in sop[:3])
        sections.append(f"相关操作规范：\n{brief}")
    return [
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": "\n\n".join(sections)},
    ]


def make_plan(task: str, skills: list[dict], sop: list[dict]) -> list[PlanStep]:
    """生成计划。解析失败重试一次，仍失败则抛 ValueError（不返回空计划）。"""
    messages = _build_messages(task, skills, sop)
    last_error: Exception | None = None

    for _ in range(2):
        message = chat(messages)
        try:
            data = _extract_json(message.get("content", ""))
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

        raw_steps = data.get("steps") or []
        steps = [
            PlanStep(
                id=index,
                intent=str(item.get("intent", "")).strip(),
                expected=str(item.get("expected", "")).strip(),
                tool_hint=(item.get("tool_hint") or None),
            )
            for index, item in enumerate(raw_steps, start=1)
            if isinstance(item, dict) and item.get("intent")
        ]

        if not steps:
            last_error = ValueError("模型返回了空计划")
            continue

        return steps[:MAX_STEPS]

    raise ValueError(f"无法得到有效计划：{last_error}")
