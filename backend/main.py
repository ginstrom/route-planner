from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from backend.config import get_settings
from backend.db import get_engine, get_session, init_db
from backend.graph import get_graph, load_scenario, patch_edge, reset_graph, seed_default_graph
from backend.models import (
    DirectSolveRequest,
    DirectSolveResponse,
    EdgePatch,
    GraphRead,
    PlanRequest,
    PlanResponse,
    ScenarioLoad,
    TraceExplainRequest,
    TraceExplainResponse,
    TraceRead,
)
from backend.planner import explain_trace, plan_route
from backend.solver import solve_route
from backend.trace import fetch_trace


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(get_engine()) as session:
        seed_default_graph(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    api = APIRouter(prefix=settings.api_prefix)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/graph")
    def read_graph(session: Session = Depends(get_session)) -> GraphRead:
        return get_graph(session)

    @api.patch("/graph/edges/{edge_id}")
    def update_edge(
        edge_id: str,
        patch: EdgePatch,
        session: Session = Depends(get_session),
    ):
        return patch_edge(session, edge_id, patch)

    @api.post("/graph/reset")
    def reset_graph_route(session: Session = Depends(get_session)) -> GraphRead:
        return reset_graph(session)

    @api.post("/graph/load-scenario")
    def apply_scenario(
        request: ScenarioLoad,
        session: Session = Depends(get_session),
    ) -> GraphRead:
        return load_scenario(session, request.scenario_id)

    @api.post("/plan/solve-direct")
    def solve_direct(
        request: DirectSolveRequest,
        session: Session = Depends(get_session),
    ) -> DirectSolveResponse:
        return solve_route(get_graph(session), request)

    @api.post("/plan")
    def plan(request: PlanRequest, session: Session = Depends(get_session)) -> PlanResponse:
        return plan_route(session, request)

    @api.get("/traces/{trace_id}")
    def get_trace(trace_id: str, session: Session = Depends(get_session)) -> TraceRead:
        try:
            return TraceRead.model_validate(fetch_trace(session, trace_id))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/traces/{trace_id}/explain")
    def explain_trace_route(
        trace_id: str,
        request: TraceExplainRequest,
        session: Session = Depends(get_session),
    ) -> TraceExplainResponse:
        try:
            return explain_trace(session, trace_id, request)
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail.lower() else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc

    app.include_router(api)
    return app


app = create_app()
