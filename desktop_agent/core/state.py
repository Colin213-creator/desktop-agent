"""一次任务在内存中的状态。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskState:
    task: str
    plan: list = field(default_factory=list)
    step_idx: int = 0
    failures: int = 0
    status: str = "pending"
