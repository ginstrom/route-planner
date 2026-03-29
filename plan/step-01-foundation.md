# Step 01: Foundation Commits

## Purpose

Establish the repo skeleton, runtime setup, and shared contracts. Complete these tasks before any graph, solver, or LLM work.

## Commit Tasks

### TB-01 Create backend skeleton

- Scope:
  - create `backend/`
  - create `backend/main.py`
  - create package directories for `graph`, `solver`, `planner`, `trace`
  - register placeholder routers
- Definition of done:
  - backend imports cleanly
  - app starts with placeholder routes
- Suggested commit:
  - `chore(TB-01): scaffold backend app`

### TB-02 Create frontend skeleton

- Scope:
  - create `frontend/`
  - create Vue 3 + Vite app shell
  - create placeholder three-panel layout
- Definition of done:
  - frontend dev server renders a single-page shell
- Suggested commit:
  - `chore(TB-02): scaffold frontend app shell`

### TB-03 Add backend dependencies and config

- Depends on:
  - `TB-01`
- Scope:
  - add FastAPI, SQLModel, OR-tools, Anthropic client, test dependencies
  - add backend config loading for `.env`
- Definition of done:
  - dependency install succeeds
  - app can read expected env vars
- Suggested commit:
  - `chore(TB-03): add backend dependencies and config`

### TB-04 Add frontend dependencies and stores scaffold

- Depends on:
  - `TB-02`
- Scope:
  - add Pinia and frontend test tooling
  - create empty graph/run/trace stores
- Definition of done:
  - app boots with Pinia wired in
- Suggested commit:
  - `chore(TB-04): add frontend state scaffolding`

### TB-05 Add Docker and environment scaffolding

- Depends on:
  - `TB-01`
  - `TB-02`
  - `TB-03`
  - `TB-04`
- Scope:
  - backend Dockerfile
  - frontend Dockerfile
  - `docker-compose.yml`
  - `.env.example`
- Definition of done:
  - both services can start through Docker Compose
- Suggested commit:
  - `chore(TB-05): add docker compose and env scaffolding`

### TB-06 Add database bootstrap

- Depends on:
  - `TB-03`
- Scope:
  - implement `backend/db.py`
  - create session management and startup init
- Definition of done:
  - SQLite file initializes on app startup
- Suggested commit:
  - `feat(TB-06): add database bootstrap`

### TB-07 Define core backend models

- Depends on:
  - `TB-06`
- Scope:
  - node model
  - edge model
  - run model
  - trace model
  - route request/result schemas
- Definition of done:
  - models serialize and validate expected shapes
- Suggested commit:
  - `feat(TB-07): define core backend models`

## Exit Gate

Do not start Step 02 until the app boots, the database initializes, and the core model contracts are stable.
