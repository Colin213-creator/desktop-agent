"""程序启动。"""

from __future__ import annotations

import subprocess

# 模型常用中文程序名，Windows 的 start 命令只认可执行名
ALIASES = {
    "计算器": "calc",
    "记事本": "notepad",
    "画图": "mspaint",
    "资源管理器": "explorer",
    "命令提示符": "cmd",
}


def open_app(name: str) -> dict:
    resolved = ALIASES.get(str(name).strip(), str(name).strip())
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", resolved],
            shell=False,
        )
    except OSError as exc:
        return {"error": f"启动失败：{exc}"}
    return {"ok": True, "action": "open_app", "app": resolved}
