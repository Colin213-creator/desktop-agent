"""Ollama 调用封装：对话、向量、健康检查。"""

from __future__ import annotations

from typing import Iterable

import requests

from .config import load_settings


def _post(path: str, payload: dict, timeout: int = 120) -> dict:
    settings = load_settings()
    resp = requests.post(f"{settings.ollama_base}{path}", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    timeout: int = 120,
) -> dict:
    """发一次对话请求，返回 assistant 的 message 字典。"""
    settings = load_settings()
    payload: dict = {
        "model": model or settings.model_main,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    return _post("/api/chat", payload, timeout).get("message", {})


def embed(texts: Iterable[str], model: str | None = None, timeout: int = 120) -> list[list[float]]:
    """把一批文本转成向量。"""
    settings = load_settings()
    payload = {"model": model or settings.model_embed, "input": list(texts)}
    return _post("/api/embed", payload, timeout).get("embeddings", [])


def health() -> dict:
    """探测模型是否可用。任何异常都转成返回值，不向上抛。"""
    settings = load_settings()
    try:
        data = _post("/api/show", {"model": settings.model_main}, timeout=10)
        return {
            "ok": True,
            "model": settings.model_main,
            "capabilities": data.get("capabilities", []),
        }
    except Exception as exc:  # 网络、超时、模型缺失都走这里
        return {
            "ok": False,
            "model": settings.model_main,
            "capabilities": [],
            "error": str(exc),
        }
