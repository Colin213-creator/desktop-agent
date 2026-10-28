from desktop_agent.memory import knowledge
from desktop_agent.memory.knowledge import KnowledgeBase


def _fake_embed(texts):
    # 所有片段给同一个向量，逼排名只能靠关键词
    return [[1.0, 0.0] for _ in texts]


def test_ingest_markdown_splits_by_heading(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "embed", _fake_embed)
    doc = tmp_path / "sop.md"
    doc.write_text("# 报销\n先填单。\n## 审批\n找主管。", encoding="utf-8")

    kb = KnowledgeBase(tmp_path / "idx")
    count = kb.ingest(doc)

    assert count >= 2
    assert kb.search("报销要做什么")[0].heading


def test_keyword_overlap_breaks_tie(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "embed", _fake_embed)
    doc = tmp_path / "sop.md"
    doc.write_text("# 报销\n填单。\n## 审批\n找主管。", encoding="utf-8")

    kb = KnowledgeBase(tmp_path / "idx")
    kb.ingest(doc)

    top = kb.search("报销要做什么")[0]
    assert "报销" in top.text
