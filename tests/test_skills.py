from desktop_agent.memory import skills
from desktop_agent.memory.skills import Skill, SkillStore


def test_skill_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    store = SkillStore(tmp_path)

    sid = store.add(
        Skill("", "打开记事本并保存", "无", ["open_app", "type_text"], 0, 3, [])
    )

    hits = store.search("打开记事本")
    assert hits[0].id == sid


def test_record_use_updates_average(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    store = SkillStore(tmp_path)

    sid = store.add(Skill("", "保存文件", "无", ["write_file"], 0, 2, []))
    store.record_use(sid, steps=4)
    store.record_use(sid, steps=6)

    assert store.stats()["avg_steps"] == 4.0
