# LLM Candidate Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Change planner mode so the solver always generates candidates first and the LLM then selects the final route from the full accepted candidate list, with that decision recorded in the trace.

**Architecture:** Keep direct solve deterministic. In planner mode, treat the solver as the bounded search stage and add an LLM candidate-selection stage after solving. Verify that the LLM's choice matches an accepted candidate before returning it, and record the selection input/output in a dedicated trace step for explanation.

**Tech Stack:** FastAPI, Pydantic/SQLModel models, pytest, Anthropic SDK

---

### Task 1: Add Planner Tests For Candidate Choice

**Files:**
- Modify: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add a planner test that drives the Anthropic flow and expects the LLM to choose the non-cheapest candidate from the provided candidate list for a query like:

```python
"Start at A and visit C and E, but avoid visiting B if possible"
```

Assert that the planner result returns `["A", "C", "E"]`, not the cheapest deterministic route.

Add a second test asserting the candidate-selection prompt includes every accepted candidate.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k "choose_candidate or candidate_list" -v`
Expected: FAIL because the planner still returns the deterministic solver-best route and does not have a candidate-choice phase.

**Step 3: Write minimal implementation**

No implementation in this task.

**Step 4: Run test to verify it still fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k "choose_candidate or candidate_list" -v`
Expected: FAIL

**Step 5: Commit**

```bash
git add backend/tests/test_planner_api.py
git commit -m "test: add planner candidate choice coverage"
```

### Task 2: Implement Candidate-Choice Prompt And Verification

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/models.py`
- Test: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add a test for malformed or invalid candidate choice that expects strict-mode failure or fallback-mode deterministic fallback.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k "invalid_candidate_choice or choose_candidate" -v`
Expected: FAIL because no candidate-choice validation exists yet.

**Step 3: Write minimal implementation**

In `backend/planner.py`:

- add a candidate-selection prompt builder,
- send all accepted candidates to the LLM,
- parse the returned candidate choice,
- verify it matches one accepted candidate exactly,
- return the chosen candidate as the planner result,
- preserve existing planner-mode error behavior.

Add or extend response models only if needed to support structured trace payloads.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_planner_api.py -k "invalid_candidate_choice or choose_candidate" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/planner.py backend/models.py backend/tests/test_planner_api.py
git commit -m "feat: add llm candidate selection"
```

### Task 3: Add Candidate-Choice Trace Step

**Files:**
- Modify: `backend/planner.py`
- Modify: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add a planner trace test asserting a `planner.choose_candidate` step is recorded with:

- original query,
- accepted candidates given to the LLM,
- chosen candidate,
- verification result,
- fallback flag.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_planner_api.py -k choose_candidate_trace -v`
Expected: FAIL because no dedicated trace step exists.

**Step 3: Write minimal implementation**

Record the selection phase in the trace after `planner.get_candidates` and before `planner.verify_solution`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_planner_api.py -k choose_candidate_trace -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/planner.py backend/tests/test_planner_api.py
git commit -m "feat: trace llm candidate selection"
```

### Task 4: Preserve Direct Solve And Infeasible Behavior

**Files:**
- Modify: `backend/tests/test_solver_api.py`
- Modify: `backend/tests/test_planner_api.py`

**Step 1: Write the failing test**

Add or tighten regression checks proving:

- direct solve output remains deterministic,
- infeasible planner requests still skip candidate choice and return existing infeasibility behavior.

**Step 2: Run test to verify it fails**

Run: `uv run pytest backend/tests/test_solver_api.py backend/tests/test_planner_api.py -v`
Expected: Any planner/direct-solve regression is exposed here.

**Step 3: Write minimal implementation**

Adjust code so candidate choice is planner-only and only runs when accepted candidates exist.

**Step 4: Run test to verify it passes**

Run: `uv run pytest backend/tests/test_solver_api.py backend/tests/test_planner_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/tests/test_solver_api.py backend/tests/test_planner_api.py backend/planner.py backend/models.py
git commit -m "test: verify llm candidate selection integration"
```
