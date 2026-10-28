from desktop_agent.actions.registry import execute


def test_write_then_read_roundtrip(tmp_path):
    p = str(tmp_path / "a.txt")
    assert execute("write_file", {"path": p, "content": "你好"})["ok"] is True
    assert execute("read_file", {"path": p})["content"] == "你好"


def test_write_into_missing_directory_returns_error(tmp_path):
    p = str(tmp_path / "nope" / "a.txt")
    result = execute("write_file", {"path": p, "content": "x"})
    assert "error" in result
