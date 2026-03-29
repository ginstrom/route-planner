# Step 07: Trace UI Commits

## Purpose

Turn the recorded trace into the main explainability surface: summaries, step playback, graph highlighting, and candidate inspection.

## Commit Tasks

### TB-43 Implement trace store

- Depends on:
  - `TB-04`
  - `TB-23`
  - `TB-34`
- Definition of done:
  - frontend can fetch a trace and track selected step state
- Suggested commit:
  - `feat(TB-43): add trace store`

### TB-44 Build Summary tab

- Depends on:
  - `TB-36`
  - `TB-43`
- Definition of done:
  - summary shows route, cost, status, and trace-grounded explanation bullets
- Suggested commit:
  - `feat(TB-44): build summary tab`

### TB-45 Build Trace tab step list

- Depends on:
  - `TB-43`
- Definition of done:
  - steps render with type, name, summary, payloads, and latency
- Suggested commit:
  - `feat(TB-45): build trace tab`

### TB-46 Build trace stepper controls

- Depends on:
  - `TB-45`
- Definition of done:
  - prev/next/start/end navigation works
- Suggested commit:
  - `feat(TB-46): add trace stepper controls`

### TB-47 Connect trace highlights to graph canvas

- Depends on:
  - `TB-41`
  - `TB-43`
  - `TB-46`
- Definition of done:
  - selecting a trace step highlights the related graph elements
- Suggested commit:
  - `feat(TB-47): connect trace highlights to graph`

### TB-48 Build Candidates tab

- Depends on:
  - `TB-36`
  - `TB-43`
- Definition of done:
  - candidate routes, costs, selected state, and rejection reasons are visible
- Suggested commit:
  - `feat(TB-48): build candidates tab`

### TB-49 Add error and infeasible run UI states

- Depends on:
  - `TB-44`
  - `TB-45`
  - `TB-48`
- Definition of done:
  - failed and infeasible cases are understandable without developer tools
- Suggested commit:
  - `feat(TB-49): add trace error states`

## Exit Gate

Do not start Step 08 until the trace is navigable, candidate inspection works, and failure states are intelligible.
