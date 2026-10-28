from desktop_agent.actions.registry import TOOLS, execute, tool_names


def test_every_schema_has_matching_implementation():
    assert set(tool_names()) == {t["function"]["name"] for t in TOOLS}


def test_unknown_tool_returns_error_not_exception():
    result = execute("nope", {})
    assert "error" in result
