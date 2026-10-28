"""Windows 控件树定位。

控件树比截图坐标可靠得多：按钮有名字、有类型，点中的是"保存"而不是某个像素。
自绘界面（Electron、游戏）读不到控件时，再由上层回退到视觉。
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class UIElement:
    name: str
    control_type: str
    rect: tuple[int, int, int, int]   # left, top, width, height
    automation_id: str


_backend: Callable[[str, str | None, int], list[UIElement]] | None = None


def set_backend(fn: Callable[[str, str | None, int], list[UIElement]] | None) -> None:
    """替换控件树后端，供测试注入。"""
    global _backend
    _backend = fn


def _screen_size() -> tuple[int, int]:
    try:
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return (1920, 1080)


def _default_backend(name_hint: str, window_title: str | None, limit: int) -> list[UIElement]:
    """用 uiautomation 浅层遍历控件树；深度和数量都设上限，避免卡死。"""
    import uiautomation as auto

    root = auto.GetRootControl()
    if window_title:
        window = auto.WindowControl(searchDepth=1, SubName=window_title)
        if window.Exists(1):
            root = window

    found: list[UIElement] = []
    cap = max(limit * 3, 30)

    def walk(control, depth: int) -> None:
        if depth > 4 or len(found) >= cap:
            return
        try:
            children = control.GetChildren()
        except Exception:
            return
        for child in children:
            try:
                box = child.BoundingRectangle
                found.append(
                    UIElement(
                        name=child.Name or "",
                        control_type=child.ControlTypeName or "",
                        rect=(
                            int(box.left),
                            int(box.top),
                            int(box.width()),
                            int(box.height()),
                        ),
                        automation_id=child.AutomationId or "",
                    )
                )
            except Exception:
                continue
            walk(child, depth + 1)

    walk(root, 0)
    return found


def find_elements(
    name_hint: str,
    window_title: str | None = None,
    limit: int = 20,
) -> list[UIElement]:
    """按名称或 AutomationId 模糊匹配控件。"""
    backend = _backend or _default_backend
    candidates = backend(name_hint, window_title, limit) or []

    hint = (name_hint or "").strip().lower()
    if not hint:
        return candidates[:limit]

    matched = [
        element
        for element in candidates
        if hint in element.name.lower() or hint in element.automation_id.lower()
    ]
    return matched[:limit]


def click_element(element: UIElement) -> bool:
    """点控件中心。控件在屏幕外或点击失败时返回 False，由上层改走视觉。"""
    left, top, width, height = element.rect
    if width <= 0 or height <= 0:
        return False

    center_x = left + width // 2
    center_y = top + height // 2
    screen_w, screen_h = _screen_size()
    if not (0 <= center_x < screen_w and 0 <= center_y < screen_h):
        return False

    try:
        from ..actions.mouse import click

        click(center_x, center_y)
        return True
    except Exception:
        return False
