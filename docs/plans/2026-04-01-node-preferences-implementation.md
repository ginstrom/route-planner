# Node Preferences Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add soft node-avoidance preferences so planner and direct-solve flows choose the best feasible candidate that avoids specified nodes when possible.

**Architecture:** Extend the formal solve request with `avoid_nodes`, keep candidate enumeration unchanged, and add a deterministic post-enumeration selection step that ranks accepted candidates by preference violations before cost. Surface those preference facts in planner traces so explanation output stays grounded in solver-evaluated candidates.

**Tech Stack:** FastAPI, Pydantic/SQLModel models, pytest, Anthropic SDK

---

### Task 1: Formal Request Contract

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_solver_api.py`

**Step 1: Write the failing test**

Add or update a direct-solve API test that posts an explicit `avoid_nodes` field and expects it to be accepted by request validation.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_solver_api.py -k avoid_nodes -v`
Expected: FAIL because `DirectSolveRequest` does not accept `avoid_nodes`.

**Step 3: Write minimal implementation**

Add `avoid_nodes: list[str] = []` to `DirectSolveRequest`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_solver_api.py -k avoid_nodes -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_solver_api.py
git commit -m "feat: add node preference request field"
```

### Task 2: Preference-Based Candidate Selection

**Files:**
- Modify: `backend/solver.py`
- Test: `backend/tests/test_solver_api.py`

**Step 1: Write the failing test**

Add a direct solver test for:

```python
def test_direct_solve_prefers_route_without_avoided_node(client) -> None:
    response = client.post(
        "/api/plan/solve-direct",
        json={
            "start_node": "A",
            "required_visits": ["C", "E"],
            "avoid_nodes": ["B"],
            "return_to_start": False,
        },
    )

    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "C", "E"]
    assert payload["total_cost"] == 13
```

Add a second test proving the solver falls back to the cheapest feasible route when every accepted candidate includes an avoided node.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_solver_api.py -k "avoided_node or fallback" -v`
Expected: FAIL because the solver still chooses the cheapest candidate regardless of `avoid_nodes`.

**Step 3: Write minimal implementation**

In `backend/solver.py`:

- add a helper that counts visited avoided nodes for a candidate route,
- rank accepted candidates by `(avoid_node_violations, total_cost, route)`,
- keep rejected candidate behavior and infeasibility behavior unchanged.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_solver_api.py -k "avoided_node or fallback" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/solver.py backend/tests/test_solver_api.py
git commit -m "feat: rank routes by node preferences"
```

### Task 3: Natural-Language Parsing For Avoid Nodes

**Files:**
- Modify: `backend/planner.py`
- Test: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add a planner API test for:

```python
def test_planner_query_avoids_node_when_alternative_exists(client) -> None:
    response = client.post(
        "/api/plan",
        json={"query": "Start at A and visit C and E, but don't visit B unless there is no other way"},
    )

    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["route"] == ["A", "C", "E"]
```

Assert that the solve trace `solver_input` includes `"avoid_nodes": ["B"]`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k avoids_node -v`
Expected: FAIL because `_parse_request` does not extract `avoid_nodes`.

**Step 3: Write minimal implementation**

In `backend/planner.py`:

- extend `_parse_request` to extract avoid-node phrases conservatively,
- ignore unknown nodes,
- preserve current parsing for `start_node`, `required_visits`, and `return_to_start`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_planner_api.py -k avoids_node -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/planner.py backend/tests/test_planner_api.py
git commit -m "feat: parse node avoidance preferences"
```

### Task 4: Trace Facts For Preference Decisions

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add a planner trace test asserting the solve payload includes candidate preference facts, for example:

- selected route visited no avoided nodes,
- alternative cheaper route visited `B`,
- selection basis mentions the avoid-node preference.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k preference_facts -v`
Expected: FAIL because solve trace payloads do not include node-preference analysis.

**Step 3: Write minimal implementation**

Extend solve trace payload generation to include:

- request `avoid_nodes`,
- per-candidate `visited_avoid_nodes`,
- per-candidate preference-violation count,
- selected-route decision metadata.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_planner_api.py -k preference_facts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/planner.py backend/tests/test_planner_api.py
git commit -m "feat: trace node preference route selection"
```

### Task 5: Regression And Suite Verification

**Files:**
- Modify: `backend/tests/test_solver_api.py`
- Modify: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add or tighten regression assertions showing that requests without `avoid_nodes` still return the current cheapest route.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_solver_api.py backend/tests/test_planner_api.py -v`
Expected: Any regression or incomplete preference behavior is exposed here.

**Step 3: Write minimal implementation**

Adjust any remaining code or tests so the new behavior is isolated to requests that include avoid-node preferences.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_solver_api.py backend/tests/test_planner_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_solver_api.py backend/tests/test_planner_api.py backend/solver.py backend/planner.py backend/models.py
git commit -m "test: verify node preference planner behavior"
```
