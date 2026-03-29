# Step 06: Core Frontend Commits

## Purpose

Build the left panel and graph view so the user can edit the graph, compose a request, and run either the direct solver or the planner path.

## Commit Tasks

### TB-35 Implement graph store

- Depends on:
  - `TB-04`
  - `TB-09`
  - `TB-10`
  - `TB-12`
- Definition of done:
  - frontend can fetch and mutate graph state
- Suggested commit:
  - `feat(TB-35): add graph store`

### TB-36 Implement run store

- Depends on:
  - `TB-04`
  - `TB-19`
  - `TB-34`
- Definition of done:
  - frontend can execute direct and planner runs
- Suggested commit:
  - `feat(TB-36): add run store`

### TB-37 Build query builder controls

- Depends on:
  - `TB-35`
  - `TB-36`
- Scope:
  - start node select
  - required visit multi-select
  - return-to-start checkbox
  - query preview
  - Run Planner button
- Definition of done:
  - user can compose and submit a route request from the UI
- Suggested commit:
  - `feat(TB-37): build query builder controls`

### TB-38 Build edge controls table

- Depends on:
  - `TB-35`
- Definition of done:
  - user can edit costs and blocked flags from the table
- Suggested commit:
  - `feat(TB-38): build edge controls table`

### TB-39 Build scenario actions section

- Depends on:
  - `TB-35`
- Definition of done:
  - user can reset graph and load sample scenarios from the UI
- Suggested commit:
  - `feat(TB-39): build scenario actions`

### TB-40 Build SVG graph canvas

- Depends on:
  - `TB-35`
- Scope:
  - nodes
  - edges
  - cost labels
  - blocked-edge styling
- Definition of done:
  - graph renders from API data with stable positioning
- Suggested commit:
  - `feat(TB-40): build svg graph canvas`

### TB-41 Add route highlighting and traversal badges

- Depends on:
  - `TB-36`
  - `TB-40`
- Definition of done:
  - selected route is visually distinct and traversal order is visible
- Suggested commit:
  - `feat(TB-41): add route highlighting`

### TB-42 Add inline edge editing from graph interactions

- Depends on:
  - `TB-38`
  - `TB-40`
- Definition of done:
  - clicking an edge opens an inline edit affordance
- Suggested commit:
  - `feat(TB-42): add inline graph edge editing`

## Exit Gate

Do not start Step 07 until the user can edit the graph and launch both backend execution paths from the UI.
