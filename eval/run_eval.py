"""评估脚本：固定任务集，跑四组配置并统计。

四组从弱到强：
  vision  —— 只有视觉，无控件树、无 RAG
  hybrid  —— 加三档混合定位
  rag     —— 加技能库与 SOP 检索
  multi   —— 再加独立的 Verifier
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from desktop_agent.core.loop import run_task

CONFIGS = ("vision", "hybrid", "rag", "multi")
TASKS_FILE = Path(__file__).parent / "tasks.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_tasks(path: Path = TASKS_FILE) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summarize(results: list[dict]) -> dict:
    count = len(results)
    if count == 0:
        return {
            "count": 0,
            "success_rate": 0.0,
            "avg_steps": 0.0,
            "avg_seconds": 0.0,
            "false_complete_rate": 0.0,
        }

    return {
        "count": count,
        "success_rate": round(sum(1 for r in results if r.get("ok")) / count, 3),
        "avg_steps": round(sum(r.get("steps", 0) for r in results) / count, 2),
        "avg_seconds": round(sum(r.get("seconds", 0) for r in results) / count, 2),
        "false_complete_rate": round(
            sum(1 for r in results if r.get("false_complete")) / count, 3
        ),
    }


def run_suite(config: str, dry_run: bool = True) -> dict:
    if config not in CONFIGS:
        raise ValueError(f"未知配置：{config}")

    rows = []
    for item in load_tasks():
        result = run_task(
            item["task"],
            confirm_fn=lambda prompt: True,
            dry_run=dry_run,
        )
        rows.append(
            {
                "id": item["id"],
                "ok": result.status == "success",
                "steps": result.steps,
                "seconds": result.seconds,
                "false_complete": bool(item.get("trap") and result.status == "success"),
            }
        )

    summary = summarize(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{config}-{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(
        json.dumps(
            {"config": config, "dry_run": dry_run, "summary": summary, "rows": rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {"config": config, "summary": summary, "rows": rows, "output": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description="桌面智能体评估")
    parser.add_argument("--config", choices=CONFIGS, default="multi")
    parser.add_argument("--live", action="store_true", help="真正执行（默认 dry_run）")
    args = parser.parse_args()

    result = run_suite(args.config, dry_run=not args.live)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print("结果文件：", result["output"])


if __name__ == "__main__":
    main()
