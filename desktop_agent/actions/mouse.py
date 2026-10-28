"""鼠标动作。pyautogui 延迟导入，方便无桌面的环境跑测试。"""

from __future__ import annotations

from ..safety.abort import AgentAborted


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True   # 鼠标猛甩到左上角可中断
    pyautogui.PAUSE = 0.2
    return pyautogui


def _guard(call):
    """把 pyautogui 的 FailSafeException 转成能穿透工具层的急停信号。"""
    try:
        return call()
    except Exception as exc:
        if type(exc).__name__ == "FailSafeException":
            raise AgentAborted() from exc
        raise


def click(x: int, y: int) -> dict:
    pg = _pg()
    _guard(lambda: pg.click(int(x), int(y)))
    return {"ok": True, "action": "click", "x": int(x), "y": int(y)}


def move(x: int, y: int) -> dict:
    pg = _pg()
    _guard(lambda: pg.moveTo(int(x), int(y)))
    return {"ok": True, "action": "move", "x": int(x), "y": int(y)}
