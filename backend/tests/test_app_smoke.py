from fastapi.testclient import TestClient

from backend.main import create_app


def test_health_and_graph_placeholder_routes() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        graph = client.get("/api/graph")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) == 5
    assert len(graph.json()["edges"]) == 8
