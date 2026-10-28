from desktop_agent.safety.guard import classify, require_confirm


def test_read_tools_classified_as_read():
    assert classify("get_disk_usage", {"drive": "C:"}) == "read"


def test_write_to_new_file_is_not_destructive(tmp_path):
    args = {"path": str(tmp_path / "new.txt"), "content": "x"}
    assert classify("write_file", args) == "ui"


def test_write_over_existing_file_is_destructive(tmp_path):
    target = tmp_path / "old.txt"
    target.write_text("old", encoding="utf-8")
    assert classify("write_file", {"path": str(target), "content": "x"}) == "destructive"


def test_ui_actions_do_not_require_confirm():
    assert require_confirm("type_text", {"text": "hi"}, confirm_fn=lambda q: True) is True
