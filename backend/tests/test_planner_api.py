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


def _capturing_anthropic_client(*responses_or_errors):
    queue = list(responses_or_errors)
    calls: list[dict[str, object]] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            current = queue.pop(0)
            if isinstance(current, Exception):
                raise current
            return current

    return SimpleNamespace(messages=FakeMessages(), calls=calls)


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
        "planner.choose_candidate",
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


def test_planner_solve_trace_includes_graph_and_route_facts(client) -> None:
    response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit C and E"},
    )

    assert response.status_code == 200
    trace = client.get(f"/api/traces/{response.json()['trace_id']}").json()
    solve_step = next(step for step in trace["steps"] if step["name"] == "planner.solve")
    payload = solve_step["payload"]

    assert payload["status"] == "SUCCESS"
    assert payload["selected_route"]["route"] == ["A", "B", "C", "E"]
    assert payload["selected_route"]["total_cost"] == 11
    assert payload["solver_input"]["start_node"] == "A"
    assert payload["solver_input"]["required_visits"] == ["C", "E"]
    assert any(edge["edge_id"] == "B-C" and edge["cost"] == 3 and edge["blocked"] is False for edge in payload["graph_edge_facts"])
    assert any(
        candidate["route"] == ["A", "C", "E"] and candidate["total_cost"] == 13 and candidate["segments"][0]["edge_id"] == "A-C"
        for candidate in payload["candidate_routes"]
    )


def test_planner_chooses_candidate_from_llm_selection(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("graph_get_state", "tool-1", {}),
            _tool_use("scenario_get_constraints", "tool-2", {}),
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E, but avoid visiting B if possible"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","C","E"],"rationale":"This route avoids B while still visiting C and E."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post(
            "/api/plan",
            json={"query": "Start at A and visit C and E, but avoid visiting B if possible"},
        )
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "C", "E"]

    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["selected_candidate"]["route"] == ["A", "C", "E"]
    assert choose_step["payload"]["verification"]["matched_solver_candidate"] is True

    selection_call = fake_client.calls[2]
    assert '"total_cost": 11' in selection_call["messages"][0]["content"]
    assert '"total_cost": 13' in selection_call["messages"][0]["content"]
    assert 'avoid visiting B if possible' in selection_call["messages"][0]["content"]


def test_planner_plain_query_prefers_cheapest_candidate(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-1", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-2", {}),
            _tool_use("planner.solve", "tool-3", {}),
            _tool_use("planner_get_candidates", "tool-4", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","B","C","E"],"rationale":"This is the lowest-cost candidate that satisfies the request."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "B", "C", "E"]
    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["selected_candidate"]["total_cost"] == 11
    assert "lowest-cost candidate" in choose_step["payload"]["rationale"]


def test_planner_overrides_non_cheapest_llm_choice_for_plain_query(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-1", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-2", {}),
            _tool_use("planner.solve", "tool-3", {}),
            _tool_use("planner_get_candidates", "tool-4", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","C","E"],"rationale":"Most direct route."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["route"] == ["A", "B", "C", "E"]
    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["selected_candidate"]["route"] == ["A", "B", "C", "E"]
    assert choose_step["payload"]["used_fallback"] is True
    assert "lowest-cost candidate" in choose_step["payload"]["rationale"]


def test_candidate_selection_prompt_defaults_to_lowest_cost_without_soft_preferences(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-1", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-2", {}),
            _tool_use("planner.solve", "tool-3", {}),
            _tool_use("planner_get_candidates", "tool-4", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","B","C","E"],"rationale":"Lowest cost."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})

    assert response.status_code == 200
    selection_call = fake_client.calls[2]
    prompt = selection_call["messages"][0]["content"]
    assert "lowest total cost" in prompt.lower()
    assert "only choose a higher-cost candidate when the user explicitly asks for a soft tradeoff" in prompt.lower()


def test_planner_choose_candidate_trace_records_candidates_and_rationale(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("graph_get_state", "tool-1", {}),
            _tool_use("scenario_get_constraints", "tool-2", {}),
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","C","E"],"rationale":"Lower preference cost for the request."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        trace = test_client.get(f"/api/traces/{response.json()['trace_id']}").json()

    assert response.status_code == 200
    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["query"] == "Start at A and visit C and E"
    assert len(choose_step["payload"]["accepted_candidates"]) >= 2
    assert choose_step["payload"]["selected_candidate"]["route"] == ["A", "B", "C", "E"]
    assert "lowest-cost candidate" in choose_step["payload"]["rationale"]
    assert choose_step["payload"]["used_fallback"] is True


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
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","B","C","E"],"rationale":"Selected the cheapest candidate."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert trace["steps"][0]["name"] == "planner.mode"
    assert trace["steps"][0]["summary"] == "Planner mode: anthropic"


def test_planner_anthropic_ignores_old_verify_solution_turn_and_still_chooses_candidate(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-1", {"query": "Start at A and visit C and E, but avoid B"}),
            _tool_use("planner_preview_problem", "tool-2", {}),
            _tool_use("planner.solve", "tool-3", {}),
            _tool_use("planner_get_candidates", "tool-4", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","C","E"],"rationale":"Avoids B while satisfying the request."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E, but avoid B"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["route"] == ["A", "C", "E"]
    step_names = [step["name"] for step in trace["steps"]]
    assert "planner.choose_candidate" in step_names
    assert step_names.index("planner.choose_candidate") < step_names.index("planner.verify_solution")


def test_planner_fallback_mode_records_fallback(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("graph_get_state", "tool-1", {}),
            _tool_use("scenario_get_constraints", "tool-2", {}),
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        RuntimeError("anthropic candidate selection outage"),
    )

    with _build_client(monkeypatch, database_url, "anthropic_with_fallback", fake_client) as test_client:
        response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["used_fallback"] is True


def test_planner_invalid_candidate_choice_falls_back_in_fallback_mode(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("graph_get_state", "tool-1", {}),
            _tool_use("scenario_get_constraints", "tool-2", {}),
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E, but avoid visiting B if possible"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","D","E"],"rationale":"Made-up route choice."}')),
    )

    with _build_client(monkeypatch, database_url, "anthropic_with_fallback", fake_client) as test_client:
        response = test_client.post(
            "/api/plan",
            json={"query": "Start at A and visit C and E, but avoid visiting B if possible"},
        )
        payload = response.json()
        trace = test_client.get(f"/api/traces/{payload['trace_id']}").json()

    assert response.status_code == 200
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "B", "C", "E"]
    choose_step = next(step for step in trace["steps"] if step["name"] == "planner.choose_candidate")
    assert choose_step["payload"]["used_fallback"] is True
    assert choose_step["payload"]["verification"]["matched_solver_candidate"] is False


def test_trace_explain_uses_anthropic_in_anthropic_mode(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","B","C","E"],"rationale":"Selected the cheapest candidate."}')),
        _anthropic_response(_text_block("The trace shows the route A -> B -> C -> E was verified after solving candidate routes.")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        plan_response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        trace_id = plan_response.json()["trace_id"]
        response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why this route?"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["planner_mode"] == "anthropic"
    assert payload["used_fallback"] is False
    assert "verified" in payload["answer"]


def test_trace_explain_prompt_includes_candidates_even_without_candidate_trace_step(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","B","C","E"],"rationale":"Selected the cheapest candidate."}')),
        _anthropic_response(_text_block("The cheaper candidate was selected.")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        plan_response = test_client.post("/api/plan", json={"query": "Start at A and visit C and E"})
        trace_id = plan_response.json()["trace_id"]
        response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why A-B-C-E instead of A-C-E?"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert "A-C-E" in payload["llm_query"]["user_prompt"]
    assert '"total_cost": 13' in payload["llm_query"]["user_prompt"]
    assert 'Compared candidate routes' in payload["llm_query"]["user_prompt"]
    assert '"chosen_route"' in payload["llm_query"]["user_prompt"]
    assert '"alternative_route"' in payload["llm_query"]["user_prompt"]
    assert "A-C-E" in payload["llm_query"]["user_prompt"]


def test_trace_explain_prompt_includes_solve_route_facts_for_blocked_alternative(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","D","E"],"rationale":"A-B-E is blocked, so choose A-D-E."}')),
        _anthropic_response(_text_block("The blocked edge explains the rejected route.")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        test_client.patch("/api/graph/edges/B-E", json={"blocked": True})
        plan_response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        trace_id = plan_response.json()["trace_id"]
        response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why didn't you choose A-B-E instead of A-D-E?"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert 'Solve route facts' in payload["llm_query"]["user_prompt"]
    assert '"edge_id": "B-E"' in payload["llm_query"]["user_prompt"]
    assert '"blocked": true' in payload["llm_query"]["user_prompt"]


def test_trace_explain_prompt_includes_grounded_blocked_route_facts_in_anthropic_mode(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","D","E"],"rationale":"A-B-E is blocked, so choose A-D-E."}')),
        _anthropic_response(_text_block("The trace shows A-B-E uses blocked edge B-E, so A -> D -> E was chosen.")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        test_client.patch("/api/graph/edges/B-E", json={"blocked": True})
        plan_response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        trace_id = plan_response.json()["trace_id"]
        response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why didn't you choose A-B-E instead of A-D-E?"},
        )
        payload = response.json()

    explanation_call = fake_client.calls[-1]
    prompt = explanation_call["messages"][0]["content"]
    assert response.status_code == 200
    assert payload["used_fallback"] is False
    assert "Grounded explanation facts" in prompt
    assert "A-B-E is not valid because it uses blocked edge B-E" in prompt
    assert payload["answer"] == "The trace shows A-B-E uses blocked edge B-E, so A -> D -> E was chosen."


def test_trace_explain_prompt_includes_grounded_skipped_node_facts_in_anthropic_mode(monkeypatch, database_url) -> None:
    fake_client = _capturing_anthropic_client(
        _anthropic_response(
            _tool_use("parse_request", "tool-3", {"query": "Start at A and visit C and E"}),
            _tool_use("planner_preview_problem", "tool-4", {}),
            _tool_use("planner_solve", "tool-5", {}),
            _tool_use("planner_get_candidates", "tool-6", {}),
        ),
        _anthropic_response(_text_block("Complete")),
        _anthropic_response(_text_block('{"route":["A","C","E"],"rationale":"Shortest valid route after the block."}')),
        _anthropic_response(_text_block("B was skipped because it was not required, A-B was blocked, and the selected route A -> C -> E remained cheaper.")),
    )

    with _build_client(monkeypatch, database_url, "anthropic", fake_client) as test_client:
        test_client.patch("/api/graph/edges/A-B", json={"blocked": True})
        response = test_client.post(
            "/api/plan",
            json={"query": "Start at A and visit C and E"},
        )
        trace_id = response.json()["trace_id"]

        explain_response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why was node B skipped?"},
        )
        payload = explain_response.json()

    assert explain_response.status_code == 200
    prompt = fake_client.calls[-1]["messages"][0]["content"]
    assert "Grounded explanation facts" in prompt
    assert "Node B was not required by the request." in prompt
    assert "blocked edge A-B" in prompt
    assert payload["answer"] == "B was skipped because it was not required, A-B was blocked, and the selected route A -> C -> E remained cheaper."


def test_trace_explain_falls_back_when_anthropic_explanation_fails(monkeypatch, database_url) -> None:
    fake_client = _make_anthropic_client(
        RuntimeError("anthropic outage"),
        RuntimeError("anthropic explanation outage"),
    )

    with _build_client(monkeypatch, database_url, "anthropic_with_fallback", fake_client) as test_client:
        plan_response = test_client.post("/api/plan", json={"query": "Start at A and visit E"})
        trace_id = plan_response.json()["trace_id"]
        response = test_client.post(
            f"/api/traces/{trace_id}/explain",
            json={"question": "Why this route?"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["planner_mode"] == "anthropic_with_fallback"
    assert payload["used_fallback"] is True
    assert "fallback" in payload["answer"].lower()


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
