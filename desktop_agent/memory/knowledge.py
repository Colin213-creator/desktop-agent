"""SOP 知识库 RAG。

技能库存的是"以前怎么做的"，这里存的是"规定应该怎么做"。
检索用混合打分：语义相似度为主，关键词重叠为辅，避免纯向量在专有名词上失灵。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..llm import embed

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT,
    heading TEXT,
    vector_json TEXT,
    keywords_json TEXT
)
"""

MAX_CHARS = 500


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    heading: str
    vector: list[float]
    keywords: list[str]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _keyword_score(query: str, text: str) -> float:
    """用中文二元组算重叠率。比整词匹配更抗分词缺失。"""
    q = re.sub(r"\s+", "", query)
    if len(q) < 2:
        return 0.0
    grams = {q[i : i + 2] for i in range(len(q) - 1)}
    flat = re.sub(r"\s+", "", text)
    hits = sum(1 for gram in grams if gram in flat)
    return hits / len(grams)


def _split_markdown(text: str) -> list[tuple[str, str]]:
    """按标题切分，返回 (heading, body) 列表。"""
    chunks: list[tuple[str, str]] = []
    heading = ""
    body: list[str] = []

    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            if heading or body:
                chunks.append((heading, "\n".join(body).strip()))
            heading = line.strip("# ").strip()
            body = []
        else:
            body.append(line)

    if heading or body:
        chunks.append((heading, "\n".join(body).strip()))

    return [(h, b) for h, b in chunks if (h or b)]


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        from docx import Document    # 可选依赖

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


class KnowledgeBase:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "knowledge.sqlite3"
        with self._conn() as conn:
            conn.execute(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db)

    def ingest(self, path: Path) -> int:
        """导入一份文档，返回写入的片段数。"""
        path = Path(path)
        raw = _read_text(path)
        pieces = _split_markdown(raw)
        if not pieces:
            return 0

        texts = [f"{h}\n{b}".strip()[:MAX_CHARS] for h, b in pieces]
        vectors = embed(texts)

        rows = []
        for (heading, _body), text, vector in zip(pieces, texts, vectors):
            rows.append(
                (
                    uuid.uuid4().hex[:12],
                    text,
                    str(path),
                    heading,
                    json.dumps(vector),
                    json.dumps([heading], ensure_ascii=False),
                )
            )

        with self._conn() as conn:
            conn.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", rows)
        return len(rows)

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        if not query.strip():
            return []

        query_vector = embed([query])[0]
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, text, source, heading, vector_json, keywords_json FROM chunks"
            ).fetchall()

        scored = []
        for row in rows:
            vector = json.loads(row[4] or "[]")
            score = 0.7 * _cosine(query_vector, vector) + 0.3 * _keyword_score(query, row[1])
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            Chunk(
                id=row[0],
                text=row[1],
                source=row[2] or "",
                heading=row[3] or "",
                vector=json.loads(row[4] or "[]"),
                keywords=json.loads(row[5] or "[]"),
            )
            for _, row in scored[:k]
        ]

    def stats(self) -> dict:
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {"chunks": count}
