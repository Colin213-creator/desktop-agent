"""独立验证器。

关键设计：只接收「预期结果 + 执行前后截图」，不接收操作者的文字解释。
自己给自己打分是这套系统最容易失真的环节，所以上下文必须隔离。
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..config import load_settings
from ..llm import chat

VERIFIER_PROMPT = """你是桌面操作的验证者。你会看到某一步的预期结果，以及执行前后的两张截图。

判断这一步是否真的达成了目标。要求：
1. 只依据截图中的可见证据，不要猜测，也不要因为"操作做了"就认为"结果达成了"。
2. 特别注意：对话框是否仍开着、文件是否真的出现在列表里、数值是否正确。
3. 只输出 JSON，不要解释，格式：
{"action":"continue|retry|replan","reason":"简短原因","evidence":"截图中看到的具体依据"}
"""

VALID_ACTIONS = {"continue", "retry", "replan"}


@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str
    evidence: str


def _encode_image(path: Path) -> str | None:
    try:
        return base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except OSError:
        return None


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("验证结果不是 JSON")
    return json.loads(raw[start : end + 1])


def verify(expected: str, before: Path, after: Path) -> Verdict:
    """判定一步是否达成。截图缺失或输出异常一律按 retry 处理。"""
    after_b64 = _encode_image(after)
    if after_b64 is None:
        return Verdict("retry", "执行后的截图缺失，无法确认结果", "")

    before_b64 = _encode_image(before)
    images = [img for img in (before_b64, after_b64) if img]

    messages = [
        {"role": "system", "content": VERIFIER_PROMPT},
        {"role": "user", "content": f"这一步的预期结果：{expected}", "images": images},
    ]

    settings = load_settings()
    try:
        message = chat(messages, model=settings.model_verifier, timeout=60)
    except Exception as exc:
        return Verdict("retry", f"验证调用失败：{exc}", "")

    try:
        data = _extract_json(message.get("content", ""))
    except (ValueError, json.JSONDecodeError):
        return Verdict("retry", "验证结果无法解析", "")

    action = str(data.get("action", "")).strip()
    if action not in VALID_ACTIONS:
        return Verdict("retry", f"验证动作非法：{action}", "")

    return Verdict(
        action=action,
        reason=str(data.get("reason", "")),
        evidence=str(data.get("evidence", "")),
    )
