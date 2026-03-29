# Explainable Route Planner Development Plan

> Sequential implementation plan for the demo application.

## Goal

Build a single-page demo that lets a user edit a small graph, ask the LLM for a route, inspect the deterministic Google OR-tools solve path through structured traces, and review a trace-grounded summary of why the chosen route was returned.

## Plan Summary

The work should proceed in strict sequence. Each step leaves the app in a runnable state and prepares the interfaces required by the next step. The order matters: first create the project skeleton and stable contracts, then deliver the editable graph and deterministic solver, then add trace persistence, then layer in LLM orchestration, and finally build the trace-centric UI and harden the demo for repeatable use.

## Key Constraints

- Use Vue 3 + Vite for the frontend.
- Use Python 3.11 + FastAPI for the backend.
- Use SQLite via SQLModel for persistence.
- Use Google OR-tools as the deterministic routing algorithm.
- Expose solver and planner behavior through API/tool boundaries that append trace steps.
- Treat graph state as fresh for each run rather than diffing against a previous run.
- The planner may reformulate the user query into a cleaner formal problem before solving.
- Do not implement previous-run comparison or diff features.

## Execution Order

1. [Step 01: Scaffold the application and shared contracts](./step-01-foundation.md)
2. [Step 02: Implement graph state, scenarios, and reset semantics](./step-02-graph-state.md)
3. [Step 03: Deliver the deterministic OR-tools solver API](./step-03-solver-api.md)
4. [Step 04: Persist runs and traces with append-only step recording](./step-04-trace-persistence.md)
5. [Step 05: Implement planner tools and LLM orchestration](./step-05-llm-orchestration.md)
6. [Step 06: Build the graph editor and LLM query UI](./step-06-frontend-core.md)
7. [Step 07: Build the trace viewer, summaries, and candidate inspection](./step-07-trace-ui.md)
8. [Step 08: Verify, document, and package the demo](./step-08-hardening.md)

## Deliverable Shape Per Step

Each step file contains:

- purpose and dependency context
- concrete deliverables
- ordered implementation tasks
- verification checklist
- exit criteria for moving to the next step

## Scope Removed From Original Spec

- Remove `POST /api/compare-runs`.
- Remove the Diff tab.
- Remove all previous-run and cost-delta comparison work.

## Notes For The Implementor

- Keep the direct solver path working even after the LLM path is introduced. It is the fastest way to validate graph and solver behavior.
- Treat the trace as a product feature, not a debug log. Every stored step should have a human-readable summary and graph highlight metadata where possible.
- Keep explanation generation grounded in stored trace/result data only. Do not surface hidden chain-of-thought.
