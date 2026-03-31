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
