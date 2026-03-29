# Step 03: Solver API Commits

## Purpose

Deliver the deterministic Google OR-tools solve path that will back both direct runs and planner tool calls.

## Commit Tasks

### TB-14 Define solver input/output contracts

- Depends on:
  - `TB-07`
  - `TB-13`
- Scope:
  - route request schema
  - route result schema
  - candidate schema
  - infeasibility payload schema
- Definition of done:
  - solver interfaces are stable and documented in code
- Suggested commit:
  - `feat(TB-14): define solver contracts`

### TB-15 Implement OR-tools graph translation

- Depends on:
  - `TB-14`
- Scope:
  - map nodes/edges into OR-tools-compatible structures
  - enforce symmetric costs and blocked-edge removal
- Definition of done:
  - translated graph matches input constraints exactly
- Suggested commit:
  - `feat(TB-15): translate graph state for ortools`

### TB-16 Implement deterministic solve path

- Depends on:
  - `TB-15`
- Scope:
  - fixed-seed solve
  - best-route extraction
  - total-cost calculation
- Definition of done:
  - repeated identical requests return identical outputs
- Suggested commit:
  - `feat(TB-16): add deterministic ortools solve`

### TB-17 Implement candidate generation

- Depends on:
  - `TB-16`
- Scope:
  - generate stable top candidates from the deterministic solve approach
  - include rejection reasons
- Definition of done:
  - candidate list ordering and reasons are stable across identical runs
- Suggested commit:
  - `feat(TB-17): generate solver candidates`

### TB-18 Implement infeasibility reporting

- Depends on:
  - `TB-16`
- Scope:
  - structured `INFEASIBLE` status
  - explanation payload for impossible requests
- Definition of done:
  - infeasible requests return structured JSON rather than generic failure
- Suggested commit:
  - `feat(TB-18): add infeasibility reporting`

### TB-19 Expose direct solve endpoint

- Depends on:
  - `TB-17`
  - `TB-18`
- Scope:
  - `POST /api/plan/solve-direct`
- Definition of done:
  - endpoint returns route, cost, status, and candidates
- Suggested commit:
  - `feat(TB-19): add direct solve endpoint`

## Exit Gate

Do not start Step 04 until direct solving is deterministic and returns clean JSON for success and infeasible cases.
