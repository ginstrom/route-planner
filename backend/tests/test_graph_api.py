def test_get_graph_returns_seeded_default_graph(client) -> None:
    response = client.get("/api/graph")

    assert response.status_code == 200
    payload = response.json()

    assert [node["id"] for node in payload["nodes"]] == ["A", "B", "C", "D", "E"]
    assert len(payload["edges"]) == 8
    assert payload["edges"][0]["source"] == "A"
    assert payload["edges"][0]["target"] == "B"
    assert payload["edges"][0]["cost"] == 4
    assert payload["edges"][0]["blocked"] is False


def test_patch_edge_updates_cost_and_blocked_state(client) -> None:
    response = client.patch(
        "/api/graph/edges/A-B",
        json={"cost": 11, "blocked": True},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["id"] == "A-B"
    assert updated["cost"] == 11
    assert updated["blocked"] is True

    graph = client.get("/api/graph").json()
    edge = next(item for item in graph["edges"] if item["id"] == "A-B")
    assert edge["cost"] == 11
    assert edge["blocked"] is True


def test_reset_restores_defaults(client) -> None:
    client.patch("/api/graph/edges/A-B", json={"cost": 12, "blocked": True})

    response = client.post("/api/graph/reset")

    assert response.status_code == 200
    payload = response.json()
    edge = next(item for item in payload["edges"] if item["id"] == "A-B")
    assert edge["cost"] == 4
    assert edge["blocked"] is False


def test_load_scenario_applies_named_mutations(client) -> None:
    response = client.post("/api/graph/load-scenario", json={"scenario_id": "single_block"})

    assert response.status_code == 200
    payload = response.json()
    edge = next(item for item in payload["edges"] if item["id"] == "B-E")
    assert edge["blocked"] is True

    cost_spike = client.post("/api/graph/load-scenario", json={"scenario_id": "cost_spike"})
    assert cost_spike.status_code == 200
    edge = next(item for item in cost_spike.json()["edges"] if item["id"] == "A-C")
    assert edge["cost"] == 20
