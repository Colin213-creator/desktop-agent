"""键盘动作。中文无法用 write() 逐键发送，统一走剪贴板粘贴。"""

from __future__ import annotations

from ..safety.abort import AgentAborted


def _pg():
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.2
    return pyautogui


def _guard(call):
    try:
        return call()
    except Exception as exc:
        if type(exc).__name__ == "FailSafeException":
            raise AgentAborted() from exc
        raise


def type_text(text: str) -> dict:
    try:
        import pyperclip

        pyperclip.copy(text)
        pg = _pg()
        _guard(lambda: pg.hotkey("ctrl", "v"))
        method = "clipboard"
    except Exception:
        pg = _pg()
        _guard(lambda: pg.write(text, interval=0.01))
        method = "keyboard"
    return {"ok": True, "action": "type_text", "chars": len(text), "method": method}


def press_keys(keys: list[str]) -> dict:
    pg = _pg()
    _guard(lambda: pg.hotkey(*keys))
    return {"ok": True, "action": "press_keys", "keys": keys}
