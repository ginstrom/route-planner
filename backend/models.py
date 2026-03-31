from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class NodeRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    label: str
    x: float
    y: float


class EdgeRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source: str
    target: str
    cost: int
    blocked: bool = False


class NodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    x: float
    y: float


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    target: str
    cost: int
    blocked: bool


class GraphRead(BaseModel):
    nodes: list[NodeRead]
    edges: list[EdgeRead]


class EdgePatch(BaseModel):
    cost: int | None = Field(default=None, ge=1)
    blocked: bool | None = None


class ScenarioLoad(BaseModel):
    scenario_id: str


class CandidateRoute(BaseModel):
    route: list[str]
    total_cost: int | None
    status: str
    rejection_reason: str | None = None


class DirectSolveRequest(BaseModel):
    start_node: str
    required_visits: list[str]
    return_to_start: bool = False


class DirectSolveResponse(BaseModel):
    status: str
    route: list[str]
    total_cost: int | None
    candidates: list[CandidateRoute]
    infeasibility_reason: str | None = None


class RunRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    mode: str
    status: str = "PENDING"
    result_payload: dict[str, object] | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceStepRecord(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    trace_id: str = Field(index=True)
    run_id: str = Field(index=True)
    step_index: int
    step_type: str
    name: str
    summary: str
    payload: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    highlights: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON))
    latency_ms: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceRead(BaseModel):
    trace_id: str
    run_id: str
    steps: list[dict[str, object]]


class PlanRequest(BaseModel):
    query: str


class PlanResponse(BaseModel):
    run_id: str
    trace_id: str
    status: str
    route: list[str]
    total_cost: int | None
    candidates: list[CandidateRoute]
    summary: str
