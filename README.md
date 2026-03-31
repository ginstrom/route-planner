# Route Planner

A demo application for an LLM explainability article/talk. It shows how an AI agent can solve a route-planning problem using tool calls — and how you can expose each reasoning step to users in a transparent, auditable trace.

The backend uses Claude (via the Anthropic API) to interpret natural-language routing requests, call structured tools to inspect the graph and constraints, and invoke an OR-Tools solver. Every step is recorded so the frontend can replay what the model did and why.

## Architecture

- **Backend** — FastAPI + SQLModel + OR-Tools + Anthropic SDK (Python)
- **Frontend** — React + Vite (TypeScript)
- **Planner modes** — `local` (deterministic), `anthropic`, or `anthropic_with_fallback`

## Installation

### Prerequisites

- Python 3.11+, [uv](https://github.com/astral-sh/uv)
- Node.js 18+

### Backend

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e . --group dev
```

### Frontend

```bash
cd frontend && npm install
```

## Usage

### Local development

**Backend** (runs on `http://localhost:8000`):

```bash
uv run --python .venv/bin/python uvicorn backend.main:app --reload
```

**Frontend** (runs on `http://localhost:5173`):

```bash
cd frontend && npm run dev
```

Set `ANTHROPIC_API_KEY` in your environment (or a `.env` file) to use the Anthropic planner. The planner mode is controlled by `PLANNER_MODE`:

| Value | Behavior |
|-------|----------|
| `local` | Deterministic local planner (no API key needed) |
| `anthropic` | Claude tool-call loop |
| `anthropic_with_fallback` | Claude first, falls back to local on failure |

`ANTHROPIC_MODEL` defaults to `claude-3-haiku-20240307`.

### Docker Compose

```bash
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

### Demo flow

1. Open the frontend in a browser.
2. Select a scenario (`single_block`, `cost_spike`, `infeasible`, etc.).
3. Enter a natural-language query, e.g. `Start at A and visit C and E`.
4. Click **Run Planner**.
5. Review the summary, trace steps, and candidate list in the right panel.
6. Switch to the `infeasible` scenario and run `Start at A and visit E` to see how the model explains an infeasible result.

## Running tests

```bash
# Backend
uv run --python .venv/bin/python pytest backend/tests -q

# Frontend
cd frontend && npm test
```
