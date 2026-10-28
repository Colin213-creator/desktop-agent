"""风险分级与确认门。

设计要点：确认门必须包住执行（`guarded_execute`），不能写成
"先执行、再询问"。未知工具一律按高危处理，失败方向偏安全。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

READ_TOOLS = {
    "get_disk_usage",
    "check_port",
    "get_system_info",
    "list_dir",
    "read_file",
    "screenshot",
    "find_elements",
}

UI_TOOLS = {
    "click",
    "move",
    "type_text",
    "press_keys",
    "open_app",
}

DESTRUCTIVE_TOOLS = {
    "delete_file",
    "shutdown",
    "restart",
}

Risk = str  # "read" | "ui" | "destructive"


def classify(tool: str, args: dict | None = None) -> Risk:
    """判定一个工具调用的风险等级。未知工具按 destructive 处理。"""
    if tool in READ_TOOLS:
        return "read"
    if tool in DESTRUCTIVE_TOOLS:
        return "destructive"
    if tool == "write_file":
        target = Path(str((args or {}).get("path", "")))
        # 覆盖已有文件会丢数据，按高危处理
        return "destructive" if target.exists() else "ui"
    if tool in UI_TOOLS:
        return "ui"
    return "destructive"


def _ask(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in {"y", "yes", "是", "确认"}
    except (EOFError, KeyboardInterrupt):
        return False


def require_confirm(
    tool: str,
    args: dict,
    confirm_fn: Callable[[str], bool] | None = None,
) -> bool:
    """高危操作返回用户是否同意；非高危直接放行。"""
    if classify(tool, args) != "destructive":
        return True

    ask = confirm_fn or _ask
    prompt = f"\n⚠ 高危操作：{tool}  {args}\n确认执行？(y/N) "
    try:
        return bool(ask(prompt))
    except (EOFError, KeyboardInterrupt):
        return False


def guarded_execute(
    tool: str,
    args: dict,
    confirm_fn: Callable[[str], bool] | None = None,
    execute_fn: Callable[[str, dict], dict] | None = None,
) -> dict:
    """先过确认门，再执行。这是主循环唯一允许调用工具的方式。"""
    risk = classify(tool, args)
    if not require_confirm(tool, args, confirm_fn):
        return {"blocked": True, "risk": risk, "reason": "用户拒绝执行"}

    if execute_fn is None:
        from ..actions.registry import execute as default_execute

        execute_fn = default_execute
    return execute_fn(tool, args)
