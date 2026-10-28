"""四角色确定性路由。

不是让几个 agent 自由对话，而是用状态机决定"下一步该谁说话"。
好处是每一步都可预测、可测试、可回放。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.verifier import Verdict


@dataclass(frozen=True)
class Route:
    action: str
    next_role: str


# Verifier 只能看到"应该达成什么"和"看到了什么"。
# operator 的自我解释被物理过滤掉，而不是靠提示词请求它忽略。
VERIFIER_ALLOWED_ROLES = {"observation", "expected", "screenshot"}


def decide(verdict: Verdict, failures: int, max_failures: int = 3) -> Route:
    """根据验证结论和累计失败次数决定下一个角色。"""
    if failures >= max_failures:
        return Route(action="replan", next_role="recoverer")

    if verdict.action == "continue":
        return Route(action="continue", next_role="operator")
    if verdict.action == "retry":
        return Route(action="retry", next_role="operator")
    return Route(action="replan", next_role="planner")


def role_context(role: str, history: list[dict]) -> list[dict]:
    """按角色裁剪上下文。Verifier 拿不到操作者的推理文字。"""
    if role != "verifier":
        return list(history)
    return [
        message
        for message in history
        if message.get("role") in VERIFIER_ALLOWED_ROLES
    ]
