from desktop_agent.actions.registry import TOOLS, execute, tool_names


def test_every_schema_has_matching_implementation():
    assert set(tool_names()) == {t["function"]["name"] for t in TOOLS}


def test_unknown_tool_returns_error_not_exception():
    result = execute("nope", {})
    assert "error" in result


def test_ui_actions_are_registered():
    names = set(tool_names())
    assert {"click", "move", "type_text", "press_keys", "open_app"} <= names


def test_unknown_argument_is_rejected_with_hint():
    result = execute("open_app", {"app_name": "计算器"})
    assert "error" in result
    assert "name" in result["error"]
