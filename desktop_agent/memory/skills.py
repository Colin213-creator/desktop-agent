"""技能库 RAG。

每次任务成功后，把"任务描述 + 工具序列"存成一条技能；下次来相似任务时，
先用向量检索召回，命中就先复用，失败再退回现场规划。
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..llm import embed

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    precondition TEXT,
    tools_json TEXT,
    success_count INTEGER NOT NULL,
    total_steps REAL NOT NULL,
    vector_json TEXT,
    last_used TEXT
)
"""


@dataclass
class Skill:
    id: str
    task: str
    precondition: str
    tools: list[str]
    success_count: int
    avg_steps: float
    vector: list[float]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SkillStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "skills.sqlite3"
        with self._conn() as conn:
            conn.execute(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db)

    def add(self, skill: Skill) -> str:
        """写入一条技能。空 id 自动生成。

        avg_steps 被视为"一次已观察样本"，因此 success_count 从 1 起算。
        """
        skill_id = skill.id or uuid.uuid4().hex[:8]
        vector = skill.vector or (embed([skill.task])[0] if skill.task else [])
        now = datetime.now().isoformat(timespec="seconds")

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO skills VALUES (?,?,?,?,?,?,?,?)",
                (
                    skill_id,
                    skill.task,
                    skill.precondition,
                    json.dumps(skill.tools, ensure_ascii=False),
                    1,
                    float(skill.avg_steps),
                    json.dumps(vector),
                    now,
                ),
            )
        return skill_id

    def search(self, query: str, k: int = 3) -> list[Skill]:
        """按语义相似度召回技能，低于 0.5 的丢弃。"""
        if not query.strip():
            return []
        query_vector = embed([query])[0]

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, task, precondition, tools_json, success_count, "
                "total_steps, vector_json FROM skills"
            ).fetchall()

        scored = []
        for row in rows:
            vector = json.loads(row[6] or "[]")
            score = _cosine(query_vector, vector)
            if score >= 0.5:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Skill(
                id=row[0],
                task=row[1],
                precondition=row[2] or "",
                tools=json.loads(row[3] or "[]"),
                success_count=row[4],
                avg_steps=round(row[5] / row[4], 2) if row[4] else 0.0,
                vector=json.loads(row[6] or "[]"),
            )
            for _, row in scored[:k]
        ]

    def record_use(self, skill_id: str, steps: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE skills SET success_count = success_count + 1, "
                "total_steps = total_steps + ?, last_used = ? WHERE id = ?",
                (float(steps), datetime.now().isoformat(timespec="seconds"), skill_id),
            )

    def stats(self) -> dict:
        with self._conn() as conn:
            count, total_steps, total_runs = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(total_steps), 0), "
                "COALESCE(SUM(success_count), 0) FROM skills"
            ).fetchone()
        return {
            "count": count,
            "avg_steps": round(total_steps / total_runs, 2) if total_runs else 0.0,
        }
