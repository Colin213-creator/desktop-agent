"""屏幕截图与坐标换算。

视觉模型返回的是 0–1000 的归一化坐标，而 Windows 开了 125%/150% 缩放后
截图尺寸与实际像素不一致，必须在这里统一换算，否则点击会整体偏移。
"""

from __future__ import annotations

import ctypes
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

NORMALIZED = 1000


@dataclass(frozen=True)
class ScreenShot:
    path: Path
    width: int
    height: int
    scale: float
    active_window: str
    cursor: tuple[int, int]


_backend: Callable[[Path], tuple] | None = None


def set_backend(fn: Callable[[Path], tuple] | None) -> None:
    """替换截图后端。测试注入假后端，避免依赖真实桌面。"""
    global _backend
    _backend = fn


def _dpi_scale() -> float:
    try:
        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        dpi = user32.GetDpiForSystem()
        return round(dpi / 96.0, 4) if dpi else 1.0
    except Exception:
        return 1.0


def _active_window() -> str:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


def _cursor_pos() -> tuple[int, int]:
    try:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)
    except Exception:
        return (0, 0)


def _default_backend(path: Path) -> tuple:
    import mss
    import mss.tools

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        mss.tools.to_png(raw.rgb, raw.size, output=str(path))

    return (
        path.stat().st_size,
        raw.size[0],
        raw.size[1],
        _dpi_scale(),
        _active_window(),
        _cursor_pos(),
    )


def capture(out_dir: Path) -> ScreenShot:
    """截一张全屏图并返回描述信息。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"shot_{datetime.now():%Y%m%d_%H%M%S_%f}.png"

    fn = _backend or _default_backend
    _size, width, height, scale, window, cursor = fn(path)

    return ScreenShot(
        path=path,
        width=int(width),
        height=int(height),
        scale=float(scale),
        active_window=window,
        cursor=(int(cursor[0]), int(cursor[1])),
    )


def to_absolute(nx: int, ny: int, shot: ScreenShot) -> tuple[int, int]:
    """把 0–1000 的归一化坐标换算成屏幕绝对像素。"""
    x = nx / NORMALIZED * shot.width * shot.scale
    y = ny / NORMALIZED * shot.height * shot.scale
    return (int(round(x)), int(round(y)))
