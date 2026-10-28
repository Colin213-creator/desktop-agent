from eval.run_eval import summarize


def test_summary_computes_rates():
    rows = [
        {"ok": True, "steps": 4, "seconds": 10, "false_complete": False},
        {"ok": False, "steps": 8, "seconds": 20, "false_complete": True},
    ]

    s = summarize(rows)

    assert s["success_rate"] == 0.5
    assert s["false_complete_rate"] == 0.5
    assert s["avg_steps"] == 6
