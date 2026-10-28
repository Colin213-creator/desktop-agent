"""命令行入口。

    python -m desktop_agent --health          检查模型
    python -m desktop_agent "打开计算器"       演练模式，只规划不执行
    python -m desktop_agent "打开计算器" --live  真正执行
    python -m desktop_agent --serve           启动本地网页
"""

from __future__ import annotations

import argparse

from .core.loop import run_task
from .llm import health


def main() -> int:
    parser = argparse.ArgumentParser(prog="desktop_agent", description="桌面智能体")
    parser.add_argument("task", nargs="*", help="用自然语言描述任务")
    parser.add_argument("--live", action="store_true", help="真正操作桌面（默认 dry-run）")
    parser.add_argument("--health", action="store_true", help="检查模型是否可用")
    parser.add_argument("--serve", action="store_true", help="启动本地网页")
    args = parser.parse_args()

    if args.health:
        info = health()
        print(info)
        return 0 if info.get("ok") else 1

    if args.serve:
        import uvicorn

        from .ui.server import create_app

        runner = lambda task: run_task(task, dry_run=not args.live)
        uvicorn.run(create_app(None, runner), host="127.0.0.1", port=8000)
        return 0

    if not args.task:
        parser.print_help()
        return 1

    result = run_task(" ".join(args.task), dry_run=not args.live)
    print(f"状态：{result.status}")
    print(f"步数：{result.steps}")
    print(f"耗时：{result.seconds}s")
    print(f"说明：{result.answer}")
    print(f"轨迹：{result.run_dir}")
    return 0 if result.status == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
