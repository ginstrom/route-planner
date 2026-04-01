# Route Trace Facts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve solver-ready graph costs and blocked-edge facts in the trace so the route explainer can answer questions about rejected or unavailable routes from execution evidence.

**Architecture:** Keep the existing graph snapshot and scenario diff steps, then enrich `planner.solve` with a normalized decision-evidence payload that includes graph edge facts, solver input, chosen route breakdown, and compared candidate route breakdowns. Feed that normalized payload into the explainer prompt and local fallback so explanation quality depends on explicit trace evidence rather than reconstruction across multiple steps.

**Tech Stack:** FastAPI, SQLModel, Pydantic, Python tests with pytest

---

### Task 1: Add regression tests for trace-carried route facts

**Files:**
- Modify: `backend/tests/test_planner_api.py`
- Modify: `backend/tests/test_trace_api.py`

**Step 1: Write the failing tests**

Add tests that require:
- `planner.solve` trace payload to include normalized graph edge facts and route analysis data.
- explanation prompts to include blocked/cost-aware solve facts.
- fallback explanations to mention blocked routes when the named alternative is impossible because of blocked edges.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_planner_api.py backend/tests/test_trace_api.py -q`
Expected: FAIL because the current trace payload only stores the final route summary.

**Step 3: Write minimal implementation**

Implement the smallest backend changes needed to produce the richer solve payload and consume it in explanations.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_planner_api.py backend/tests/test_trace_api.py -q`
Expected: PASS

### Task 2: Enrich solver trace payload and explanation inputs

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/solver.py`
- Modify: `backend/models.py` if a new structured payload model is justified

**Step 1: Write the failing test**

Use the tests from Task 1 as the red phase for this work.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_planner_api.py backend/tests/test_trace_api.py -q`
Expected: FAIL with missing keys or missing blocked-route explanation details.

**Step 3: Write minimal implementation**

Add helpers that:
- serialize graph edges into solver-ready facts
- compute per-route edge breakdowns and totals from the graph
- derive explicit comparison facts for named alternatives
- store those facts on the `planner.solve` trace step
- include those facts in the LLM explanation prompt and fallback explanation path

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_planner_api.py backend/tests/test_trace_api.py -q`
Expected: PASS

### Task 3: Verify no regression in direct solver and planner flow

**Files:**
- Test: `backend/tests/test_solver_api.py`
- Test: `backend/tests/test_planner_api.py`
- Test: `backend/tests/test_trace_api.py`

**Step 1: Run focused regression checks**

Run: `pytest backend/tests/test_solver_api.py backend/tests/test_planner_api.py backend/tests/test_trace_api.py -q`
Expected: PASS

**Step 2: Review trace-facing behavior**

Confirm that successful and blocked-route explanation paths both expose explicit trace evidence rather than inferred-only prose.

**Step 3: Commit**

```bash
git add docs/plans/2026-04-01-route-trace-facts.md backend/planner.py backend/solver.py backend/tests/test_planner_api.py backend/tests/test_trace_api.py
git commit -m "feat: trace solver route facts for explanations"
```
