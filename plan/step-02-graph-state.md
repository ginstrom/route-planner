# Step 02: Graph State Commits

## Purpose

Create the canonical graph API, sample scenarios, and fresh-graph-per-run behavior. This phase defines the state that the solver and planner consume.

## Commit Tasks

### TB-08 Seed the default graph

- Depends on:
  - `TB-07`
- Scope:
  - seed five nodes with fixed coordinates
  - seed eight undirected edges with default costs
- Definition of done:
  - fresh database contains exact default graph from the spec
- Suggested commit:
  - `feat(TB-08): seed default graph`

### TB-09 Implement graph read service

- Depends on:
  - `TB-08`
- Scope:
  - graph state read service
  - `GET /api/graph`
- Definition of done:
  - API returns default graph payload
- Suggested commit:
  - `feat(TB-09): add graph read endpoint`

### TB-10 Implement edge patch service

- Depends on:
  - `TB-09`
- Scope:
  - update edge cost
  - update blocked state
  - `PATCH /api/graph/edges/{edge_id}`
- Definition of done:
  - edge updates persist and validate correctly
- Suggested commit:
  - `feat(TB-10): add edge patch endpoint`

### TB-11 Implement scenario presets

- Depends on:
  - `TB-08`
- Scope:
  - `baseline`
  - `single_block`
  - `cost_spike`
  - `infeasible`
- Definition of done:
  - each scenario applies the expected graph mutations
- Suggested commit:
  - `feat(TB-11): add graph scenario presets`

### TB-12 Implement reset and utility actions

- Depends on:
  - `TB-10`
  - `TB-11`
- Scope:
  - `POST /api/graph/reset`
  - `POST /api/graph/load-scenario`
  - optional clear-blocks and restore-costs helpers
- Definition of done:
  - graph can be returned to exact defaults from any edited state
- Suggested commit:
  - `feat(TB-12): add graph reset and scenario actions`

### TB-13 Finalize fresh-graph-per-run semantics

- Depends on:
  - `TB-12`
- Scope:
  - decide and implement how each run gets fresh graph state
  - document the behavior
- Definition of done:
  - starting a new run cannot inherit stale graph state from a prior run
- Suggested commit:
  - `feat(TB-13): enforce fresh graph state per run`

## Exit Gate

Do not start Step 03 until graph editing, reset, scenarios, and per-run state semantics are deterministic.
