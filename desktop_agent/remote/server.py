"""远程被控端。

目标不是低延迟远程桌面，而是"另一台设备下一句话，这台机器执行并回传状态"。
核心循环不 import 本模块，远程层挂了不影响本地演示。
"""

from __future__ import annotations

import asyncio
import threading
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator


class TaskBody(BaseModel):
    task: str

    @field_validator("task")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("任务不能为空")
        return value.strip()


def create_remote_app(
    run_task_fn: Callable[[str], object],
    token: str,
) -> FastAPI:
    """run_task_fn 通常是 core.loop.run_task。"""
    app = FastAPI(title="桌面智能体 · 被控端")
    state: dict = {"current": None}

    def check(token_header: str | None) -> None:
        if not token or token_header != token:
            raise HTTPException(status_code=401, detail="令牌无效")

    @app.post("/api/task")
    def submit(
        body: TaskBody,
        x_agent_token: str | None = Header(default=None),
    ) -> dict:
        check(x_agent_token)
        state["current"] = body.task
        threading.Thread(
            target=run_task_fn, args=(body.task,), daemon=True
        ).start()
        return {"accepted": True, "task": body.task}

    @app.get("/api/state")
    def snapshot(x_agent_token: str | None = Header(default=None)) -> dict:
        check(x_agent_token)
        return {"current": state["current"]}

    @app.websocket("/agent")
    async def agent_stream(socket: WebSocket, token_q: str | None = None) -> None:
        if token_q != token:
            await socket.close(code=1008)
            return

        await socket.accept()
        try:
            while True:
                await socket.send_json({"type": "status", "task": state["current"]})
                await asyncio.sleep(2)
        except WebSocketDisconnect:
            return

    return app
