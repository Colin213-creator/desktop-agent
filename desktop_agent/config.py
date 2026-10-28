"""项目配置：默认值集中在这里，允许用环境变量覆盖。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    ollama_base: str = "http://127.0.0.1:11434"
    model_main: str = "gemma4:31b-cloud"
    # 验证器必须能看图：deepseek-r1:1.5b 无 vision，不能用于视觉验证
    model_verifier: str = "gemma4:31b-cloud"
    model_embed: str = "bge-m3"
    max_steps: int = 30
    max_seconds: int = 600
    max_llm_calls: int = 120
    runs_dir: Path = Path("runs")
    sandbox_dir: Path = Path("runs/_sandbox")


def _int_env(name: str, default: int) -> int:
    """读整数环境变量；写错了就用默认值，不让配置错误拖垮整个程序。"""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings() -> Settings:
    defaults = Settings()
    return Settings(
        ollama_base=os.environ.get("DA_OLLAMA_BASE", defaults.ollama_base).rstrip("/"),
        model_main=os.environ.get("DA_MODEL_MAIN", defaults.model_main),
        model_verifier=os.environ.get("DA_MODEL_VERIFIER", defaults.model_verifier),
        model_embed=os.environ.get("DA_MODEL_EMBED", defaults.model_embed),
        max_steps=_int_env("DA_MAX_STEPS", defaults.max_steps),
        max_seconds=_int_env("DA_MAX_SECONDS", defaults.max_seconds),
        max_llm_calls=_int_env("DA_MAX_LLM_CALLS", defaults.max_llm_calls),
        runs_dir=Path(os.environ.get("DA_RUNS_DIR", str(defaults.runs_dir))),
        sandbox_dir=Path(os.environ.get("DA_SANDBOX_DIR", str(defaults.sandbox_dir))),
    )
