# Trace Explanation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a middle-pane trace explanation query box that asks why the planner chose a route, using the completed trace and planner mode-specific explanation behavior.

**Architecture:** Add a trace-scoped explanation endpoint in the FastAPI backend and keep all mode branching on the server so `local`, `anthropic`, and `anthropic_with_fallback` behave consistently with planner execution. Add a dedicated frontend explanation store and render the new query card directly beneath the route graph so the UI can ask questions about the trace shown in the right pane.

**Tech Stack:** FastAPI, SQLModel, Anthropic SDK, Vue 3, Pinia, Vitest, pytest

---

### Task 1: Backend explanation API contract

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/tests/test_trace_api.py`

**Step 1: Write the failing test**

Add a backend API test that posts to `/api/traces/{trace_id}/explain` with a question and expects a structured response containing `trace_id`, `planner_mode`, `used_fallback`, and `answer`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_trace_api.py -k explain -q`
Expected: FAIL because the endpoint and request/response models do not exist yet.

**Step 3: Write minimal implementation**

Add request/response models for trace explanation and wire the endpoint into `backend/main.py`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_trace_api.py -k explain -q`
Expected: PASS

### Task 2: Mode-aware explanation service

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/trace.py`
- Modify: `backend/models.py`
- Test: `backend/tests/test_trace_api.py`
- Test: `backend/tests/test_planner_api.py`

**Step 1: Write the failing tests**

Add tests for:
- local mode returning a deterministic explanation grounded in trace/result data
- anthropic mode using the Anthropic client to answer explanation questions
- anthropic fallback mode returning fallback output and `used_fallback=true` when Anthropic explanation fails

**Step 2: Run tests to verify they fail**

Run: `uv run pytest backend/tests/test_trace_api.py backend/tests/test_planner_api.py -k explain -q`
Expected: FAIL because the explanation service does not exist.

**Step 3: Write minimal implementation**

Persist enough run context to recover the original planner task prompt and final result, then implement a trace explanation service that:
- loads the run + trace
- validates the question
- builds a grounded prompt or deterministic mock explanation
- mirrors planner mode behavior for local / anthropic / fallback

**Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_trace_api.py backend/tests/test_planner_api.py -k explain -q`
Expected: PASS

### Task 3: Frontend explanation query box

**Files:**
- Modify: `frontend/src/App.test.ts`
- Create: `frontend/src/stores/explanation.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/api.ts` (if helper changes are needed)

**Step 1: Write the failing test**

Add a UI test that runs the planner, verifies an explanation query card appears under the graph, submits a question, and renders the returned explanation plus fallback state when provided.

**Step 2: Run test to verify it fails**

Run: `npm test -- --run frontend/src/App.test.ts`
Expected: FAIL because the explanation store, fetch path, and UI do not exist.

**Step 3: Write minimal implementation**

Add a dedicated Pinia store for explanation state, reset it when planner-derived state is cleared, and render the middle-pane query card beneath the route graph with loading/error/fallback states.

**Step 4: Run test to verify it passes**

Run: `npm test -- --run frontend/src/App.test.ts`
Expected: PASS

### Task 4: Verification

**Files:**
- Modify: `docs/plans/2026-03-31-trace-explanation-implementation.md`

**Step 1: Run backend verification**

Run: `uv run pytest backend/tests/test_trace_api.py backend/tests/test_planner_api.py -q`
Expected: PASS

**Step 2: Run frontend verification**

Run: `npm test -- --run frontend/src/App.test.ts`
Expected: PASS

**Step 3: Record any follow-up risks**

Note residual risks only if a live Anthropic path cannot be fully integration-tested in the local environment.
