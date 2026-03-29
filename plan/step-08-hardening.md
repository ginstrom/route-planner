# Step 08: Hardening Commits

## Purpose

Close testing, documentation, and demo-readiness gaps so the project can be implemented and presented without tribal knowledge.

## Commit Tasks

### TB-50 Add backend tests for graph APIs

- Depends on:
  - `TB-12`
- Definition of done:
  - graph API tests cover read, patch, reset, and scenario load
- Suggested commit:
  - `test(TB-50): cover graph APIs`

### TB-51 Add backend tests for solver behaviors

- Depends on:
  - `TB-19`
- Definition of done:
  - solver tests cover baseline, blocked, cost-spike, and infeasible flows
- Suggested commit:
  - `test(TB-51): cover solver behaviors`

### TB-52 Add backend tests for planner traces

- Depends on:
  - `TB-34`
- Definition of done:
  - planner tests confirm expected tool sequence and partial trace preservation
- Suggested commit:
  - `test(TB-52): cover planner traces`

### TB-53 Add frontend tests for graph and controls

- Depends on:
  - `TB-42`
- Definition of done:
  - control and graph interactions are covered by component/store tests
- Suggested commit:
  - `test(TB-53): cover graph controls`

### TB-54 Add frontend tests for trace UI

- Depends on:
  - `TB-49`
- Definition of done:
  - trace navigation and summary rendering are covered by tests
- Suggested commit:
  - `test(TB-54): cover trace ui`

### TB-55 Add end-to-end demo flow

- Depends on:
  - `TB-52`
  - `TB-54`
- Definition of done:
  - one test exercises graph edit, planner run, trace inspection, and candidate inspection
- Suggested commit:
  - `test(TB-55): add end-to-end demo flow`

### TB-56 Write demo runbook

- Depends on:
  - `TB-55`
- Definition of done:
  - a new operator can run and present the demo from the documentation
- Suggested commit:
  - `docs(TB-56): add demo runbook`

### TB-57 Remove stale spec references

- Depends on:
  - `TB-56`
- Definition of done:
  - no docs or code mention compare-runs or a Diff tab
- Suggested commit:
  - `docs(TB-57): remove stale diff references`

## Exit Gate

The plan is complete when tests pass, the demo runbook is accurate, and all removed-scope references are gone.
