# Route Planner Design

## Goal

Build an explainable route-planning demo where a user can edit a small weighted graph, run either a direct deterministic solver or an LLM-orchestrated planner, and inspect a stored trace that explains how the final route was produced.

## Architecture

- Backend: FastAPI service organized into `graph`, `solver`, `trace`, and `planner` modules.
- Persistence: SQLite via SQLModel for graph state, runs, and append-only trace steps.
- Deterministic optimization: Google OR-tools performs route solving for both the direct API and the planner tool path.
- Planner orchestration: an LLM reformulates natural-language requests and chooses tools, but all route decisions are grounded in deterministic backend tools whose outputs are persisted in the trace.
- Frontend: Vue 3 + Vite single-page app with Pinia stores for graph, run, and trace state.
- Python environment management: backend dependencies are installed and run through a project-local `uv` virtualenv.
- Delivery shape: the full app must be runnable via Docker Compose for demo use.

## Data Flow

1. Backend startup initializes the database and seeds the default graph when needed.
2. Frontend loads graph state from `GET /api/graph` and uses it as the single source of truth for the graph canvas and edge controls.
3. Graph edits, resets, and scenario loads persist through API calls.
4. Direct runs call `POST /api/plan/solve-direct` with a formal route request and receive deterministic solver output.
5. Planner runs call `POST /api/plan`, which creates a run, opens a trace, orchestrates tool calls, and returns the final result plus `trace_id`.
6. The trace store fetches `GET /api/traces/{trace_id}` and drives step playback plus graph highlights in the UI.

## Error Handling

- Invalid graph edits return structured API errors without mutating unrelated state.
- Expected unsatisfied routing requests return structured `INFEASIBLE` results rather than generic failures.
- Unexpected planner failures still preserve the run record and all trace steps written before the failure.
- Trace steps remain append-only with stable ordering and human-readable summaries.

## Testing Strategy

- Backend tests cover graph APIs, deterministic solver behavior, and planner trace sequencing.
- Frontend tests cover stores, query controls, graph editing, trace navigation, and candidate rendering.
- One end-to-end test covers graph edit, planner run, trace inspection, and candidate review.

## Execution Approach

Implement in vertical slices following the repository plan order:

1. Foundation and contracts
2. Graph state and scenarios
3. Deterministic solver API
4. Trace persistence
5. LLM orchestration
6. Frontend graph and run UI
7. Trace and candidate UI
8. Hardening, tests, and docs

## Environment Constraints

- Use `uv venv` and `uv pip install` for Python dependency management instead of relying on the system interpreter.
- Keep backend and frontend startup commands aligned with container execution so local development and Docker Compose use the same entrypoints where practical.

## Anthropic Runtime Modes

- Planner execution is controlled by config rather than hard-coded behavior.
- Supported `planner_mode` values:
  - `local`: always use the local deterministic orchestration path.
  - `anthropic`: require a live Anthropic tool loop and fail the run if the API call or tool loop fails.
  - `anthropic_with_fallback`: try the Anthropic tool loop first, then record a fallback trace step and continue with the local orchestration path if the Anthropic path fails.
- Anthropic usage must preserve the existing traced tool contract. The model may decide tool order, but the executed tool surface remains `graph.get_state`, `scenario.get_constraints`, `parse_request`, `planner.preview_problem`, `planner.solve`, `planner.get_candidates`, `planner.verify_solution`, and `planner.explain_infeasibility`.
- The trace must record planner mode selection, Anthropic failures or fallback activation, and executed tool steps without storing chain-of-thought.
