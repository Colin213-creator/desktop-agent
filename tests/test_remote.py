from fastapi.testclient import TestClient

from desktop_agent.remote.server import create_remote_app


def test_rejects_missing_or_wrong_token():
    app = create_remote_app(lambda task: None, "secret")
    client = TestClient(app)

    assert client.post("/api/task", json={"task": "x"}).status_code == 401
    assert (
        client.post("/api/task", json={"task": "x"}, headers={"X-Agent-Token": "bad"})
        .status_code
        == 401
    )
    assert (
        client.post(
            "/api/task", json={"task": "x"}, headers={"X-Agent-Token": "secret"}
        ).status_code
        == 200
    )


def test_empty_task_rejected():
    app = create_remote_app(lambda task: None, "secret")
    client = TestClient(app)
    resp = client.post(
        "/api/task", json={"task": "   "}, headers={"X-Agent-Token": "secret"}
    )
    assert resp.status_code == 422
