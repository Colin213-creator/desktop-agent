"""截图脱敏与模型路由。

桌面智能体每一步都要把屏幕交给模型，所以这里是一道闸门：
先裁剪（默认只截活动窗口），再对敏感矩形涂黑，最后才决定发云端还是走本地模型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Mask:
    """需要涂黑的一块矩形，坐标是 (left, top, right, bottom) 像素。"""

    rect: tuple[int, int, int, int]


@dataclass
class PrivacyPolicy:
    window_only: bool = True
    masks: list[Mask] = field(default_factory=list)
    cloud_upload: bool = True

    def allow_fullscreen(self) -> bool:
        return not self.window_only

    def upload_label(self) -> str:
        return "已脱敏上传" if self.cloud_upload else "仅本地"


def redact(src: Path, masks: list[Mask], out: Path) -> Path:
    """把指定矩形涂黑后另存。越界坐标自动裁剪到图像范围内。"""
    from PIL import Image, ImageDraw

    img = Image.open(src).convert("RGB")
    width, height = img.size
    draw = ImageDraw.Draw(img)

    for mask in masks:
        left, top, right, bottom = (int(v) for v in mask.rect)
        left = max(0, min(left, width - 1))
        top = max(0, min(top, height - 1))
        right = max(left + 1, min(right, width - 1))
        bottom = max(top + 1, min(bottom, height - 1))
        draw.rectangle([left, top, right, bottom], fill=(0, 0, 0))

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def route_model(policy: PrivacyPolicy, task: str) -> str:
    """决定这一步用云端还是本地模型。"""
    return "local" if not policy.cloud_upload else "cloud"
