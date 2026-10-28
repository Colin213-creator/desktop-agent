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
