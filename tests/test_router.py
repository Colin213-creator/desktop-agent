from desktop_agent.core.verifier import Verdict
from desktop_agent.orchestration.router import decide, role_context


def test_three_failures_trigger_recoverer():
    route = decide(Verdict("retry", "没成", ""), failures=3)
    assert route.next_role == "recoverer"


def test_continue_goes_back_to_operator():
    route = decide(Verdict("continue", "成了", "截图显示窗口已打开"), failures=0)
    assert route.action == "continue"
    assert route.next_role == "operator"


def test_replan_goes_to_planner():
    route = decide(Verdict("replan", "路径不对", ""), failures=1)
    assert route.next_role == "planner"


def test_verifier_context_excludes_operator_reasoning():
    history = [
        {"role": "operator", "content": "我点了保存"},
        {"role": "observation", "content": "dialog_open"},
    ]
    ctx = role_context("verifier", history)
    assert all(message["role"] != "operator" for message in ctx)
    assert any(message["role"] == "observation" for message in ctx)
