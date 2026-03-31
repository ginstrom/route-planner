# SVG Route Graph Debugging Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Find and fix the reason the route graph pane is blank in the browser without replacing the SVG renderer prematurely.

**Architecture:** Start by proving where failure occurs in the current pipeline: backend graph payload, frontend fetch/store application, conditional rendering, SVG markup, or CSS/layout. Add the smallest possible observability and regression coverage, then implement the narrowest fix that restores visible nodes and edges. Only evaluate a renderer change if evidence shows the SVG path is fundamentally blocking required behavior.

**Tech Stack:** Vue 3, Pinia, Vite, Vitest, FastAPI

---

### Task 1: Reproduce the blank graph with evidence

**Files:**
- Inspect: `README.md`
- Inspect: `frontend/src/App.vue`
- Inspect: `frontend/src/stores/graph.ts`
- Inspect: `backend/graph.py`

**Step 1: Start the backend**

Run:

```bash
uv run --python .venv/bin/python uvicorn backend.main:app --reload
```

Expected: FastAPI starts on `http://localhost:8000`.

**Step 2: Start the frontend**

Run:

```bash
cd frontend && npm run dev
```

Expected: Vite starts on `http://localhost:5173`.

**Step 3: Capture the actual failure mode**

In the browser, open the app and record:

1. Whether the center panel contains the fallback message from `graph-state`.
2. Whether the `<svg data-testid="route-graph-svg">` element exists in DevTools.
3. Whether `<circle>` and `<line>` elements exist inside the SVG.
4. Any browser-console errors or warnings.
5. The network result for `GET /api/graph`.

Expected: One concrete failure class is identified:
- backend fetch failed
- store rejected payload
- SVG exists but children are missing
- SVG children exist but are not visible

**Step 4: Save the evidence**

Record exact console messages, network status, and DOM observations in the work log or issue notes before changing code.

**Step 5: Commit checkpoint if you created any repro notes in the repo**

```bash
git add <notes-if-any>
git commit -m "docs: capture svg graph repro evidence"
```

### Task 2: Verify the data path before touching rendering

**Files:**
- Inspect: `frontend/src/stores/graph.ts`
- Inspect: `frontend/src/api.ts`
- Inspect: `backend/graph.py`
- Test: `frontend/src/App.test.ts`

**Step 1: Confirm backend payload shape**

Run:

```bash
curl -sS http://localhost:8000/api/graph
```

Expected: JSON with non-empty `nodes` and `edges`, and finite numeric `x`/`y` values.

**Step 2: Confirm the frontend store accepts the payload**

Add temporary logging only if needed in `frontend/src/stores/graph.ts` around:
- fetch success
- `applyGraph(graph)`
- validation failure branches

Expected: You can tell whether the blank pane is caused by request failure or store rejection.

**Step 3: Add or update a regression test for the observed failure**

If the failure is a bad payload case, add a focused test in `frontend/src/App.test.ts` or a new graph-store test that reproduces it directly.

Expected: A failing test exists before the fix.

**Step 4: Run the targeted frontend test**

Run:

```bash
cd frontend && npm test -- App.test.ts
```

Expected: The new or updated test fails for the current bug.

**Step 5: Commit checkpoint**

```bash
git add frontend/src/App.test.ts frontend/src/stores/graph.ts
git commit -m "test: reproduce blank svg graph failure"
```

### Task 3: Inspect DOM and CSS visibility, not just SVG existence

**Files:**
- Inspect: `frontend/src/App.vue`

**Step 1: Check whether the SVG is mounted**

In DevTools, inspect the center pane and verify:

1. The `v-if` branch chose the SVG instead of `.graph-state`.
2. The SVG has a non-zero rendered box.
3. The `viewBox` is `0 0 520 360`.

Expected: Either the SVG is absent because the state branch is wrong, or it is present with a real layout box.

**Step 2: Check child geometry**

Inspect one rendered node and one edge:

1. `circle[cx][cy][r]`
2. `line[x1][y1][x2][y2]`
3. `text` labels

Expected: Numeric coordinates match backend values and are inside the viewBox.

**Step 3: Check computed styles**

Verify that:

1. `.graph-svg` is not hidden by `display`, `visibility`, `opacity`, or zero height.
2. `.node-circle`, `.node-label`, and `.edge-line` have visible fill/stroke colors.
3. No overlay or parent stacking context is covering the SVG.

Expected: Either a CSS/layout problem is identified or rendering remains the primary suspect.

**Step 4: If visibility is the issue, add the smallest fix**

Possible fixes:
- set explicit `height` instead of relying on `min-height`
- add `display: block` to the SVG
- adjust fill/stroke contrast
- remove accidental overlay or clipping

**Step 5: Commit checkpoint**

```bash
git add frontend/src/App.vue
git commit -m "fix: restore svg graph visibility"
```

### Task 4: Fix the true root cause with the smallest change

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/stores/graph.ts`
- Modify: `frontend/src/api.ts`
- Modify: `backend/graph.py`
- Test: `frontend/src/App.test.ts`

**Step 1: Choose the narrowest fix based on evidence**

Examples:
- API/proxy issue: fix base URL or proxy assumptions
- validation issue: improve payload handling or error surfacing
- conditional rendering issue: correct the `v-if` branch inputs
- SVG visibility issue: fix the sizing/styling bug

**Step 2: Implement only the minimal production change**

Do not switch renderers in this task unless the failure clearly comes from an SVG limitation rather than a bug.

**Step 3: Keep or add diagnostics that help future failures**

Allowed:
- concise console errors
- clearer graph-state message
- tighter validation errors

Avoid:
- noisy permanent debug logs
- speculative refactors

**Step 4: Run focused tests**

Run:

```bash
cd frontend && npm test -- App.test.ts
```

Expected: The previously failing regression test now passes.

**Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/stores/graph.ts frontend/src/api.ts frontend/src/App.test.ts backend/graph.py
git commit -m "fix: resolve blank route graph svg"
```

### Task 5: Verify end-to-end behavior in the browser

**Files:**
- Verify: `frontend/src/App.vue`
- Verify: `frontend/src/App.test.ts`

**Step 1: Reload the app with both servers running**

Expected: The route graph visibly shows nodes and edges on initial load.

**Step 2: Exercise core interactions**

Verify:

1. Start-node select is populated.
2. Scenario apply updates the graph.
3. Run Planner highlights route edges.
4. Reset Graph restores baseline.

**Step 3: Confirm error behavior still works**

Simulate or test a failed `/api/graph` response and confirm the fallback message is shown instead of a silent blank pane.

**Step 4: Run all frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: Frontend test suite passes.

**Step 5: Optional backend smoke**

Run:

```bash
uv run --python .venv/bin/python pytest backend/tests -q
```

Expected: Backend API tests still pass if any server-side graph behavior changed.

### Task 6: Re-evaluate the renderer only if evidence demands it

**Files:**
- Inspect: `frontend/src/App.vue`
- Inspect: `frontend/package.json`

**Step 1: Decide whether the issue was architectural or incidental**

If the fix was:
- a fetch/proxy bug
- a store validation bug
- a Vue conditional rendering bug
- a CSS/layout bug

then keep SVG.

**Step 2: Consider a different renderer only if one of these is true**

1. The graph needs pan/zoom, drag, or force layout that is becoming awkward in hand-written SVG.
2. The graph size is growing enough that DOM-based SVG becomes a performance problem.
3. You need graph-editing features better served by a dedicated library.

**Step 3: If reconsideration is still needed, write a separate design note**

Compare:
- hand-written SVG
- SVG with a graph helper library
- canvas/WebGL

Expected: Renderer replacement is treated as a separate scoped decision, not folded into the bug fix.
