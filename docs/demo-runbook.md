# Route Planner Demo Runbook

## Local Development

### Backend

1. Create the Python environment:
   `uv venv .venv`
2. Install backend dependencies:
   `uv pip install --python .venv/bin/python -e . --group dev`
3. Run the API:
   `uv run --python .venv/bin/python uvicorn backend.main:app --reload`

### Frontend

1. Install frontend dependencies:
   `cd frontend && npm install`
2. Run the Vite app:
   `npm run dev`

The frontend expects the backend at `http://localhost:8000` unless `VITE_API_BASE_URL` is set.

## Planner Modes

Backend planner behavior is controlled by `PLANNER_MODE`:

- `local`: use the deterministic local planner orchestration only
- `anthropic`: require a live Anthropic tool loop
- `anthropic_with_fallback`: try Anthropic first, then fall back to the local planner if the Anthropic call fails

Anthropic settings:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (defaults to `claude-3-haiku-20240307`)

The Anthropic planner sends the system prompt as a cacheable block so prompt caching can be used when supported by the account and model.

## Docker Compose

From the repository root:

`docker compose up --build`

Services:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`

## Demo Flow

1. Open the frontend in the browser.
2. Confirm the graph and edge table load.
3. Choose a scenario such as `single_block` or `cost_spike`.
4. Build or edit the planner query, for example:
   `Start at A and visit C and E`
5. Click `Run Planner`.
6. Review the summary, trace steps, and candidate list in the right panel.
7. Switch to the `infeasible` scenario and run:
   `Start at A and visit E`
8. Confirm the UI shows the infeasible explanation and corresponding trace step.

## Verification Commands

- Backend tests:
  `uv run --python .venv/bin/python pytest backend/tests -q`
- Frontend tests:
  `cd frontend && npm test`
- Frontend build:
  `cd frontend && npm run build`
