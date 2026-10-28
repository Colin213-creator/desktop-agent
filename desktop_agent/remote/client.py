"""控制端：向被控端下发任务。"""

from __future__ import annotations

import requests


def submit_task(url: str, token: str, task: str, timeout: int = 30) -> str:
    resp = requests.post(
        f"{url.rstrip('/')}/api/task",
        json={"task": task},
        headers={"X-Agent-Token": token},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("task", task)
