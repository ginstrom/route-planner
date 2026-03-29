# Step 05: Planner and Orchestration Commits

## Purpose

Add the LLM planning path while keeping optimization deterministic. The LLM orchestrates API/tool usage and reformulates requests; Google OR-tools performs the solve.

## Commit Tasks

### TB-25 Implement `graph.get_state`

- Depends on:
  - `TB-09`
  - `TB-22`
- Definition of done:
  - tool returns graph JSON and appends a trace step
- Suggested commit:
  - `feat(TB-25): add graph.get_state tool`

### TB-26 Implement `scenario.get_constraints`

- Depends on:
  - `TB-12`
  - `TB-22`
- Definition of done:
  - tool returns blocked edges and modified costs in clean JSON
- Suggested commit:
  - `feat(TB-26): add scenario.get_constraints tool`

### TB-27 Implement request reformulation and `parse_request`

- Depends on:
  - `TB-14`
  - `TB-22`
- Definition of done:
  - natural-language requests can be transformed into a formal route request
  - `parse_request` is recorded in the trace
- Suggested commit:
  - `feat(TB-27): add request reformulation step`

### TB-28 Implement `planner.preview_problem`

- Depends on:
  - `TB-27`
- Definition of done:
  - tool produces a formalized problem statement for the planner loop
- Suggested commit:
  - `feat(TB-28): add planner.preview_problem tool`

### TB-29 Implement `planner.solve`

- Depends on:
  - `TB-16`
  - `TB-22`
- Definition of done:
  - tool reuses OR-tools solver and records a trace step
- Suggested commit:
  - `feat(TB-29): add planner.solve tool`

### TB-30 Implement `planner.get_candidates`

- Depends on:
  - `TB-17`
  - `TB-22`
- Definition of done:
  - tool returns candidate list and records a trace step
- Suggested commit:
  - `feat(TB-30): add planner.get_candidates tool`

### TB-31 Implement `planner.verify_solution`

- Depends on:
  - `TB-29`
- Definition of done:
  - selected route is validated against current constraints and traced
- Suggested commit:
  - `feat(TB-31): add planner.verify_solution tool`

### TB-32 Implement `planner.explain_infeasibility`

- Depends on:
  - `TB-18`
  - `TB-22`
- Definition of done:
  - infeasible cases get a structured traced explanation
- Suggested commit:
  - `feat(TB-32): add planner.explain_infeasibility tool`

### TB-33 Implement Anthropic orchestration loop

- Depends on:
  - `TB-25`
  - `TB-26`
  - `TB-28`
  - `TB-29`
  - `TB-30`
  - `TB-31`
  - `TB-32`
- Scope:
  - tool registration
  - tool-call interception
  - run status updates
- Definition of done:
  - planner requests execute the expected sequence and persist a trace
- Suggested commit:
  - `feat(TB-33): add anthropic orchestration loop`

### TB-34 Expose `POST /api/plan`

- Depends on:
  - `TB-33`
- Definition of done:
  - endpoint returns run metadata, final result, candidates, summary, and `trace_id`
- Suggested commit:
  - `feat(TB-34): add planner endpoint`

## Exit Gate

Do not start Step 06 until the backend supports both direct solve and traced LLM-orchestrated solve.
