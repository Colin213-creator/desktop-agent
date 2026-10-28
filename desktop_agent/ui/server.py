"""本地网页：左边看画面，右边看日志，顶部急停。

界面只读状态，不直接驱动动作；核心循环不 import 这个模块。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

STATIC = Path(__file__).parent / "static"


class TaskRequest(BaseModel):
    task: str


def create_app(state_feed: Callable[[], dict] | None = None) -> FastAPI:
    """state_feed 每次调用返回当前状态，用于推送给网页。"""
    app = FastAPI(title="桌面智能体")
    state: dict = {"stopped": False, "feed": state_feed}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.post("/api/task")
    def submit(request: TaskRequest) -> dict:
        state["stopped"] = False
        return {"accepted": True, "task": request.task}

    @app.post("/api/stop")
    def stop() -> dict:
        state["stopped"] = True
        return {"stopped": True}

    @app.get("/api/state")
    def snapshot() -> dict:
        feed = state["feed"]
        payload = feed() if callable(feed) else {}
        return {"stopped": state["stopped"], "state": payload}

    @app.websocket("/ws")
    async def stream(socket: WebSocket) -> None:
        await socket.accept()
        try:
            while True:
                feed = state["feed"]
                payload = feed() if callable(feed) else {}
                await socket.send_json(
                    {"type": "state", "stopped": state["stopped"], "payload": payload}
                )
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            return

    return app
