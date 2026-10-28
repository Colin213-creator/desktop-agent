"""运行轨迹：把每一步的动作、截图和判定写进磁盘。

轨迹是回放的唯一依据，也是排查"它为什么点错了"的证据。
写盘用 UTF-8 + ensure_ascii=False，中文直接可读。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class StepRecord:
    idx: int
    tool: str
    args: dict
    risk: str
    before: str
    after: str
    verdict: str
    reason: str
    seconds: float


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class TraceWriter:
    """一次运行一个目录：task.json 存任务信息，trace.json 存逐步记录。"""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []
        self.task_meta: dict = {}

    def write_task(self, meta: dict) -> None:
        self.task_meta = dict(meta)
        _write_json(self.run_dir / "task.json", self.task_meta)

    def write_step(self, step: StepRecord) -> None:
        self.steps.append(asdict(step))

    def finalize(self, status: str) -> None:
        _write_json(
            self.run_dir / "trace.json",
            {"status": status, "steps": self.steps},
        )


def load_run(run_dir: Path) -> dict:
    """读取一次运行。文件缺失时返回空结构，不抛异常。"""
    run_dir = Path(run_dir)

    task: dict = {}
    task_file = run_dir / "task.json"
    if task_file.exists():
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            task = {}

    trace: dict = {"status": "unknown", "steps": []}
    trace_file = run_dir / "trace.json"
    if trace_file.exists():
        try:
            trace = json.loads(trace_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "task": task,
        "steps": trace.get("steps", []),
        "status": trace.get("status", "unknown"),
    }
