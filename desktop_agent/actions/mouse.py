"""鼠标动作。pyautogui 延迟导入，方便无桌面的环境跑测试。"""

from __future__ import annotations


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True   # 鼠标猛甩到左上角可中断
    pyautogui.PAUSE = 0.2
    return pyautogui


def click(x: int, y: int) -> dict:
    _pg().click(int(x), int(y))
    return {"ok": True, "action": "click", "x": int(x), "y": int(y)}


def move(x: int, y: int) -> dict:
    _pg().moveTo(int(x), int(y))
    return {"ok": True, "action": "move", "x": int(x), "y": int(y)}
