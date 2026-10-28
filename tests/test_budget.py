import time

from desktop_agent.safety.budget import Budget


def test_budget_blocks_after_max_steps():
    b = Budget(max_steps=2, max_seconds=600, max_llm_calls=10)
    b.spend_step()
    b.spend_step()
    assert b.can_continue() is False
    assert b.reason() == "超过最大步数"


def test_budget_counts_time():
    b = Budget(max_steps=10, max_seconds=0.05, max_llm_calls=10)
    time.sleep(0.06)
    assert b.can_continue() is False and "超时" in b.reason()
