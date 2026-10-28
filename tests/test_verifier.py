from desktop_agent.core import verifier
from desktop_agent.core.verifier import verify


def test_missing_after_image_forces_retry(tmp_path):
    v = verify("文件已保存", tmp_path / "a.png", tmp_path / "missing.png")
    assert v.action == "retry"
    assert "截图" in v.reason


def test_verdict_rejects_unknown_action(tmp_path, monkeypatch):
    before = tmp_path / "a.png"
    after = tmp_path / "b.png"
    before.write_bytes(b"fake")
    after.write_bytes(b"fake")

    monkeypatch.setattr(
        verifier,
        "chat",
        lambda *a, **k: {
            "content": '{"action":"looks_good","reason":"ok","evidence":"x"}'
        },
    )
    v = verify("x", before, after)
    assert v.action == "retry"
