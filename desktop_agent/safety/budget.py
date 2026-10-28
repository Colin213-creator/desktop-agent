"""步数、时长、模型调用次数的硬上限。

三个上限任意一个触顶就停，避免智能体卡在死循环里空转烧 token。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Budget:
    max_steps: int
    max_seconds: float
    max_llm_calls: int
    started_at: float = field(default_factory=time.monotonic)
    steps: int = 0
    calls: int = 0

    def spend_step(self) -> None:
        self.steps += 1

    def spend_call(self) -> None:
        self.calls += 1

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def reason(self) -> str | None:
        """返回第一个触顶原因；还有余量时返回 None。"""
        if self.steps >= self.max_steps:
            return "超过最大步数"
        if self.elapsed() > self.max_seconds:
            return "超过最大时长，已超时"
        if self.calls >= self.max_llm_calls:
            return "超过最大模型调用次数"
        return None

    def can_continue(self) -> bool:
        return self.reason() is None
