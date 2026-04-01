from backend.trace import append_trace_step, create_run, create_trace, fetch_trace, update_run


def test_run_lifecycle_persists_status_and_result(db_session) -> None:
    run = create_run(db_session, mode="planner")
    update_run(db_session, run_id=run.id, status="SUCCESS", result_payload={"route": ["A", "B"]})

    assert run.status == "SUCCESS"
    assert run.result_payload == {"route": ["A", "B"]}


def test_trace_steps_append_in_stable_order(db_session) -> None:
    run = create_run(db_session, mode="planner")
    trace = create_trace(db_session, run_id=run.id)

    append_trace_step(
        db_session,
        trace_id=trace.id,
        step_type="tool",
        name="graph.get_state",
        summary="Loaded graph",
        payload={"nodes": 5},
    )
    append_trace_step(
        db_session,
        trace_id=trace.id,
        step_type="tool",
        name="planner.solve",
        summary="Solved route",
        payload={"route": ["A", "B"]},
    )

    fetched = fetch_trace(db_session, trace.id)

    assert [step["step_index"] for step in fetched["steps"]] == [0, 1]
    assert fetched["steps"][0]["name"] == "graph.get_state"
    assert fetched["steps"][1]["name"] == "planner.solve"


def test_trace_fetch_endpoint_returns_serialized_trace(client, db_session) -> None:
    run = create_run(db_session, mode="planner")
    trace = create_trace(db_session, run_id=run.id)
    append_trace_step(
        db_session,
        trace_id=trace.id,
        step_type="tool",
        name="planner.preview_problem",
        summary="Previewed the routing problem",
        payload={"start": "A"},
    )

    response = client.get(f"/api/traces/{trace.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == trace.id
    assert payload["run_id"] == run.id
    assert payload["steps"][0]["summary"] == "Previewed the routing problem"


def test_failed_run_keeps_partial_trace(db_session) -> None:
    run = create_run(db_session, mode="planner")
    trace = create_trace(db_session, run_id=run.id)
    append_trace_step(
        db_session,
        trace_id=trace.id,
        step_type="tool",
        name="parse_request",
        summary="Parsed request",
        payload={"start": "A"},
    )
    update_run(db_session, run_id=run.id, status="FAILED", error_message="planner timeout")

    fetched = fetch_trace(db_session, trace.id)

    assert run.status == "FAILED"
    assert run.error_message == "planner timeout"
    assert len(fetched["steps"]) == 1
    assert fetched["steps"][0]["name"] == "parse_request"


def test_trace_explain_endpoint_returns_local_grounded_answer(client) -> None:
    plan_response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit C and E"},
    )
    trace_id = plan_response.json()["trace_id"]

    response = client.post(
        f"/api/traces/{trace_id}/explain",
        json={"question": "Why did you choose A-B-C-E instead of A-C-E?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == trace_id
    assert payload["planner_mode"] == "local"
    assert payload["used_fallback"] is False
    assert "A -> B -> C -> E" in payload["answer"]
    assert "A -> C -> E" in payload["answer"]
    assert "11" in payload["answer"]
    assert "13" in payload["answer"]
    assert "A-C-E" in payload["llm_query"]["user_prompt"]
    assert '"route": [' in payload["llm_query"]["user_prompt"]


def test_trace_explain_local_answer_mentions_blocked_named_alternative(client) -> None:
    client.patch("/api/graph/edges/B-E", json={"blocked": True})
    plan_response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit E"},
    )
    trace_id = plan_response.json()["trace_id"]

    response = client.post(
        f"/api/traces/{trace_id}/explain",
        json={"question": "Why didn't you choose A-B-E instead of A-D-E?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "A-B-E" in payload["answer"]
    assert "blocked" in payload["answer"].lower()
    assert "B-E" in payload["answer"]
    assert '"edge_id": "B-E"' in payload["llm_query"]["user_prompt"]
