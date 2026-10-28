"""程序启动。"""

from __future__ import annotations

import subprocess


def open_app(name: str) -> dict:
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", str(name)],
            shell=False,
        )
    except OSError as exc:
        return {"error": f"启动失败：{exc}"}
    return {"ok": True, "action": "open_app", "app": str(name)}
