def test_direct_solve_returns_deterministic_best_route(client) -> None:
    request = {
        "start_node": "A",
        "required_visits": ["C", "E"],
        "return_to_start": False,
    }

    first = client.post("/api/plan/solve-direct", json=request)
    second = client.post("/api/plan/solve-direct", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()

    payload = first.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "B", "C", "E"]
    assert payload["total_cost"] == 11
    assert payload["candidates"][0]["route"] == ["A", "B", "C", "E"]
    assert payload["candidates"][0]["total_cost"] == 11
    assert any(candidate["route"] == ["A", "C", "E"] for candidate in payload["candidates"])
    alternative = next(candidate for candidate in payload["candidates"] if candidate["route"] == ["A", "C", "E"])
    assert alternative["total_cost"] == 13


def test_direct_solve_accepts_avoid_nodes_and_prefers_route_without_avoided_node(client) -> None:
    response = client.post(
        "/api/plan/solve-direct",
        json={
            "start_node": "A",
            "required_visits": ["C", "E"],
            "avoid_nodes": ["B"],
            "return_to_start": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "C", "E"]
    assert payload["total_cost"] == 13
    assert payload["candidates"][0]["route"] == ["A", "B", "C", "E"]


def test_direct_solve_falls_back_to_best_available_route_when_avoid_node_is_unavoidable(client) -> None:
    response = client.post(
        "/api/plan/solve-direct",
        json={
            "start_node": "A",
            "required_visits": ["B", "E"],
            "avoid_nodes": ["B"],
            "return_to_start": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "B", "E"]
    assert payload["total_cost"] == 9


def test_direct_solve_respects_blocked_edges(client) -> None:
    client.patch("/api/graph/edges/B-E", json={"blocked": True})

    response = client.post(
        "/api/plan/solve-direct",
        json={
            "start_node": "A",
            "required_visits": ["E"],
            "return_to_start": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "D", "E"]
    assert payload["total_cost"] == 9


def test_direct_solve_reports_infeasible_request(client) -> None:
    client.post("/api/graph/load-scenario", json={"scenario_id": "infeasible"})

    response = client.post(
        "/api/plan/solve-direct",
        json={
            "start_node": "A",
            "required_visits": ["E"],
            "return_to_start": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "INFEASIBLE"
    assert payload["route"] == []
    assert payload["total_cost"] is None
    assert "reachable" in payload["infeasibility_reason"]
