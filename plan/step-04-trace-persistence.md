# Step 04: Trace Persistence Commits

## Purpose

Build append-only run and trace persistence before introducing LLM orchestration. The planner should record steps into a stable storage contract, not invent one inline.

## Commit Tasks

### TB-20 Create run lifecycle service

- Depends on:
  - `TB-07`
- Scope:
  - create run
  - update status
  - store result payload
- Definition of done:
  - run lifecycle supports pending, success, failure states
- Suggested commit:
  - `feat(TB-20): add run lifecycle service`

### TB-21 Create trace lifecycle service

- Depends on:
  - `TB-20`
- Scope:
  - create trace
  - append step
  - fetch trace
- Definition of done:
  - trace steps persist in append order
- Suggested commit:
  - `feat(TB-21): add trace lifecycle service`

### TB-22 Define trace step serializer

- Depends on:
  - `TB-21`
- Scope:
  - serialize step metadata, payloads, and highlights
  - guarantee stable `step_index`
- Definition of done:
  - stored trace shape matches plan/spec
- Suggested commit:
  - `feat(TB-22): define trace step serialization`

### TB-23 Expose trace fetch endpoint

- Depends on:
  - `TB-21`
  - `TB-22`
- Scope:
  - `GET /api/traces/{trace_id}`
- Definition of done:
  - UI can fetch the full trace payload by id
- Suggested commit:
  - `feat(TB-23): add trace fetch endpoint`

### TB-24 Add timing and partial-failure helpers

- Depends on:
  - `TB-21`
- Scope:
  - latency measurement
  - partial trace preservation on failure
- Definition of done:
  - failed operations still leave retrievable trace evidence
- Suggested commit:
  - `feat(TB-24): add trace timing and failure helpers`

## Exit Gate

Do not start Step 05 until traced operations can be recorded, fetched, and preserved through failures.
