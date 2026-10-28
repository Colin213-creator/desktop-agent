from fastapi.testclient import TestClient

from desktop_agent.ui.server import create_app


def test_task_endpoint_requires_task():
    client = TestClient(create_app(lambda: None))
    assert client.post("/api/task", json={}).status_code == 422
    assert client.get("/").status_code == 200


def test_stop_endpoint_is_idempotent():
    client = TestClient(create_app(lambda: None))
    assert client.post("/api/stop").status_code == 200
    assert client.post("/api/stop").status_code == 200


def test_submit_starts_task_when_handler_provided():
    seen = []
    client = TestClient(create_app(None, lambda task: seen.append(task)))

    resp = client.post("/api/task", json={"task": "打开计算器"})

    assert resp.status_code == 200
    for _ in range(50):
        if seen:
            break
        import time
        time.sleep(0.01)
    assert seen == ["打开计算器"]
