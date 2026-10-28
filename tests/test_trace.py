from desktop_agent.memory.trace import StepRecord, TraceWriter, load_run


def test_trace_roundtrip(tmp_path):
    w = TraceWriter(tmp_path)
    w.write_task({"task": "打开记事本"})
    w.write_step(
        StepRecord(
            idx=1,
            tool="open_app",
            args={"name": "notepad"},
            risk="ui",
            before="a.png",
            after="b.png",
            verdict="continue",
            reason="已打开",
            seconds=1.2,
        )
    )
    w.finalize("success")

    data = load_run(tmp_path)
    assert data["task"]["task"] == "打开记事本"
    assert data["steps"][0]["tool"] == "open_app"
    assert data["status"] == "success"
