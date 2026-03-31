# Route Planner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the full explainable route planner demo, including deterministic solving, trace persistence, LLM orchestration, and the Vue frontend.

**Architecture:** Build the backend first in stable vertical slices: graph state, deterministic solve, trace persistence, and planner orchestration. Manage Python through a local `uv` virtualenv, keep the service entrypoints Docker-friendly, then add the frontend against those stable contracts and finish with backend/frontend/e2e verification plus a demo runbook.

**Tech Stack:** FastAPI, SQLModel, SQLite, Google OR-tools, Anthropic SDK, Vue 3, Vite, Pinia, Vitest, Playwright

---

### Task 1: Foundation

**Files:**
- Create: `backend/`
- Create: `frontend/`
- Create: `pyproject.toml`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Steps**

1. Write a failing backend smoke test for app startup and health routes.
2. Run the backend test and verify the expected failure.
3. Create the Python project config, `.venv` via `uv venv`, and install backend/test dependencies with `uv`.
4. Add the FastAPI app skeleton, configuration, and database bootstrap.
5. Re-run the backend smoke test through `uv run pytest` until it passes.
6. Create the frontend Vite/Vue shell with Pinia and a placeholder three-panel layout.
7. Add Dockerfiles and `docker-compose.yml` so the app boots through Compose.
8. Run the frontend test/build command and a Docker Compose smoke start to verify the shell passes.

### Task 2: Graph State

**Files:**
- Modify: `backend/graph/*`
- Modify: `backend/models/*`
- Test: `backend/tests/test_graph_api.py`

**Steps**

1. Write failing tests for graph read, edge patch, reset, and scenario load.
2. Run only the graph API tests and verify the expected failures.
3. Implement default graph seeding, graph read/update services, scenario presets, and reset semantics.
4. Re-run the graph API tests until they pass.

### Task 3: Deterministic Solver

**Files:**
- Modify: `backend/solver/*`
- Modify: `backend/api/*`
- Test: `backend/tests/test_solver_api.py`

**Steps**

1. Write failing tests for baseline, blocked-edge, cost-spike, and infeasible solver flows.
2. Run only the solver tests and verify the expected failures.
3. Implement route contracts, graph translation, deterministic solving, candidate generation, infeasibility reporting, and the direct solve endpoint.
4. Re-run the solver tests until they pass.

### Task 4: Trace Persistence

**Files:**
- Modify: `backend/trace/*`
- Modify: `backend/models/*`
- Test: `backend/tests/test_trace_api.py`

**Steps**

1. Write failing tests for run creation, append-only trace storage, fetch ordering, and failure preservation.
2. Run the trace tests and verify the expected failures.
3. Implement run lifecycle, trace lifecycle, step serialization, and the trace fetch endpoint.
4. Re-run the trace tests until they pass.

### Task 5: Planner Orchestration

**Files:**
- Modify: `backend/planner/*`
- Modify: `backend/main.py`
- Test: `backend/tests/test_planner_api.py`

**Steps**

1. Write failing tests for planner tool sequencing, parsed request tracing, solver tool tracing, infeasible explanation tracing, and partial trace preservation.
2. Run the planner tests and verify the expected failures.
3. Implement planner tools, request reformulation, Anthropic orchestration, run status updates, and `POST /api/plan`.
4. Re-run the planner tests until they pass.

### Task 6: Frontend Core

**Files:**
- Modify: `frontend/src/*`
- Test: `frontend/src/**/*.test.ts`

**Steps**

1. Write failing frontend tests for graph loading, edge editing, scenario actions, and run submission.
2. Run the targeted frontend tests and verify the expected failures.
3. Implement graph and run stores, the query builder, edge controls table, scenario actions, SVG graph canvas, route highlighting, and inline edge editing.
4. Re-run the targeted frontend tests until they pass.

### Task 7: Trace UI

**Files:**
- Modify: `frontend/src/*`
- Test: `frontend/src/**/*.test.ts`

**Steps**

1. Write failing frontend tests for summary rendering, trace step navigation, graph highlights, candidate inspection, and infeasible/error UI states.
2. Run the targeted trace UI tests and verify the expected failures.
3. Implement the trace store, Summary tab, Trace tab, stepper controls, candidate tab, and error-state handling.
4. Re-run the targeted tests until they pass.

### Task 8: Hardening

**Files:**
- Modify: `README.md`
- Create: `docs/demo-runbook.md`
- Test: backend, frontend, and e2e suites

**Steps**

1. Add an end-to-end demo flow test that covers graph edit, planner run, trace inspection, and candidate review.
2. Run the e2e test and verify the expected failures.
3. Implement any missing glue and documentation, including the runbook.
4. Run backend tests through `uv run pytest`, frontend tests, and the e2e test suite.
5. Run a full Docker Compose verification pass.
6. Verify the documented run flow against the implementation.

### Task 9: Anthropic Planner Modes

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/planner.py`
- Modify: `backend/tests/test_planner_api.py`
- Modify: `docs/demo-runbook.md`

**Steps**

1. Write failing planner tests for `local`, `anthropic`, and `anthropic_with_fallback` mode behavior using a fake Anthropic client.
2. Run the targeted planner tests and verify the expected failures.
3. Add config for `planner_mode`, `anthropic_api_key`, and `anthropic_model`.
4. Implement the Anthropic tool-loop adapter and fallback handling while preserving trace semantics.
5. Re-run the targeted planner tests until they pass.
6. Update the demo runbook with Anthropic mode configuration and verification notes.
