"""主循环：规划 → 执行一步 → 截图 → 验证 → 继续 / 重试 / 停止。

所有外部依赖都放在模块级名字上（make_plan / capture / operator / verify），
测试可以整体替换，不需要真的调模型或操作桌面。
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..actions.registry import TOOLS
from ..config import Settings, load_settings
from ..llm import chat
from ..memory.trace import StepRecord, TraceWriter
from ..perception.screen import ScreenShot, capture
from ..safety.budget import Budget
from ..safety.guard import classify, guarded_execute
from .planner import PlanStep, make_plan
from .state import TaskState
from .verifier import Verdict, verify

MAX_FAILURES = 3

OPERATOR_PROMPT = """你是桌面操作者。根据当前步骤和截图，从工具清单中选择一个工具完成这一步。

要求：
1. 只调用一个工具，参数要具体（坐标、文字、路径）。
2. 优先用语义工具（open_app / type_text / press_keys），不要盲目点坐标。
3. 不确定时选择更保守的动作。
"""


@dataclass
class TaskResult:
    status: str
    steps: int
    seconds: float
    answer: str
    run_dir: Path


def _image_b64(shot: ScreenShot) -> str | None:
    try:
        return base64.b64encode(Path(shot.path).read_bytes()).decode("ascii")
    except OSError:
        return None


def operator(step: PlanStep, shot: ScreenShot) -> dict:
    """默认操作者：让模型从工具清单里选一个动作。"""
    image = _image_b64(shot)
    messages = [
        {"role": "system", "content": OPERATOR_PROMPT},
        {
            "role": "user",
            "content": (
                f"当前步骤：{step.intent}\n"
                f"预期结果：{step.expected}\n"
                f"建议工具：{step.tool_hint}"
            ),
            "images": [image] if image else [],
        },
    ]

    try:
        message = chat(messages, tools=TOOLS)
    except Exception:
        return {"tool": step.tool_hint or "screenshot", "args": {}}

    calls = message.get("tool_calls") or []
    if calls:
        function = calls[0].get("function", {})
        return {
            "tool": function.get("name", ""),
            "args": function.get("arguments") or {},
        }
    return {"tool": step.tool_hint or "screenshot", "args": {}}


def run_task(
    task: str,
    confirm_fn=None,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> TaskResult:
    """跑完一个任务。dry_run=True 时只规划和选择动作，不真正执行。"""
    settings = settings or load_settings()
    started = time.monotonic()
    run_dir = Path(settings.runs_dir) / datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    writer = TraceWriter(run_dir)
    writer.write_task(
        {
            "task": task,
            "model": settings.model_main,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": dry_run,
        }
    )

    def finish(status: str, answer: str, steps: int) -> TaskResult:
        writer.finalize(status)
        return TaskResult(
            status=status,
            steps=steps,
            seconds=round(time.monotonic() - started, 2),
            answer=answer,
            run_dir=run_dir,
        )

    try:
        plan = make_plan(task, [], [])
    except Exception as exc:
        return finish("failed", f"规划失败：{exc}", 0)

    budget = Budget(settings.max_steps, settings.max_seconds, settings.max_llm_calls)
    state = TaskState(task=task, plan=plan)

    for index, step in enumerate(plan, start=1):
        blocked_reason = budget.reason()
        if blocked_reason:
            return finish("blocked", blocked_reason, state.step_idx)

        budget.spend_step()
        state.step_idx = index

        before = capture(run_dir)
        action = operator(step, before)
        tool = str(action.get("tool", ""))
        args = action.get("args") or {}
        risk = classify(tool, args)

        if dry_run:
            result = {"dry_run": True, "tool": tool, "args": args}
        else:
            result = guarded_execute(tool, args, confirm_fn=confirm_fn)
            if result.get("blocked"):
                writer.write_step(
                    StepRecord(
                        index, tool, args, risk,
                        str(before.path), "", "blocked",
                        str(result.get("reason", "")), 0.0,
                    )
                )
                return finish("blocked", f"用户拒绝执行：{tool}", state.step_idx)

        after = capture(run_dir)

        try:
            verdict = verify(step.expected, before.path, after.path)
        except Exception as exc:          # 验证器挂了不算任务失败，按重试处理
            verdict = Verdict("retry", f"验证异常：{exc}", "")

        writer.write_step(
            StepRecord(
                index, tool, args, risk,
                str(before.path), str(after.path),
                verdict.action, verdict.reason, 0.0,
            )
        )

        if verdict.action == "continue":
            state.failures = 0
            continue

        state.failures += 1
        if state.failures >= MAX_FAILURES:
            return finish(
                "failed",
                f"连续 {state.failures} 次未达成：{verdict.reason}",
                state.step_idx,
            )

    return finish("success", f"完成 {state.step_idx} 步", state.step_idx)
