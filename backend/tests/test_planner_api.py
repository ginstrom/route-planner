from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.db import get_engine
from backend.main import create_app
from backend.planner import TOOL_DEFINITIONS


def _make_anthropic_client(*responses_or_errors):
    queue = list(responses_or_errors)

    class FakeMessages:
        def create(self, **_kwargs):
            current = queue.pop(0)
            if isinstance(current, Exception):
                raise current
            return current

    return SimpleNamespace(messages=FakeMessages())


def _anthropic_response(*blocks):
    return SimpleNamespace(content=list(blocks))


def _tool_use(name, tool_id, payload):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=payload)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _build_client(monkeypatch, database_url, planner_mode, fake_client):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PLANNER_MODE", planner_mode)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_settings.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("backend.planner.get_anthropic_client", lambda _settings: fake_client)
    return TestClient(create_app())


def test_planner_run_returns_trace_and_expected_tool_sequence(client) -> None:
    response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit C and E"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "B", "C", "E"]
    assert payload["trace_id"]
    assert payload["run_id"]

    trace = client.get(f"/api/traces/{payload['trace_id']}").json()
    assert [step["name"] for step in trace["steps"]] == [
        "graph.get_state",
        "scenario.get_constraints",
        "parse_request",
        "planner.preview_problem",
        "planner.solve",
        "planner.get_candidates",
        "planner.verify_solution",
    ]


def test_planner_run_records_infeasibility_explanation(client) -> None:
    client.post("/api/graph/load-scenario", json={"scenario_id": "infeasible"})

    response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit E"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INFEASIBLE"
    assert payload["trace_id"]

    trace = client.get(f"/api/traces/{payload['trace_id']}").json()
    assert trace["steps"][-1]["name"] == "planner.explain_infeasibility"
    assert "reachable" in trace["steps"][-1]["summary"]


def test_planner_failure_preserves_partial_trace(client) -> None:
    response = client.post(
        "/api/plan",
        json={"query": "Visit E"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "FAILED"
    assert payload["trace_id"]

    trace = client.get(f"/api/traces/{payload['trace_id']}").json()
    assert [step["name"] for step in trace["steps"]] == [
        "graph.get_state",
        "scenario.get_constraints",
        "parse_request",
    ]
    assert "start node" in trace["steps"][-1]["summary"].lower()


def test_planner_anthropic_mode_executes_tool_loop(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("graph_get_state", "tool-1", {}),
            _tool_use("scenario_get_constraints", "tool-2", {}),
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
            _tool_use("planner_verify_solution", "tool-7", {}),
        ),
        _anthropic_response(_text_block("Complete")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert trace["steps"][0]["name"] == "planner.mode"
    assert trace["steps"][0]["summary"] == "Planner mode: anthropic"


def test_planner_fallback_mode_records_fallback(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(RuntimeError("anthropic outage"))

    with _build_client(monkeypatch, database_url, "anthropic_with_fallback", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert any(step["name"] == "planner.fallback" for step in trace["steps"])


def test_planner_anthropic_mode_fails_without_fallback(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(RuntimeError("anthropic outage"))

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "FAILED"
    assert trace["steps"][-1]["name"] == "planner.llm_error"


def test_anthropic_tool_names_are_provider_safe() -> None:
    for tool in TOOL_DEFINITIONS:
        assert "." not in tool["name"]
