from fastapi import HTTPException
from sqlmodel import Session, select

from backend.models import EdgePatch, EdgeRead, EdgeRecord, GraphRead, NodeRead, NodeRecord


DEFAULT_NODES = [
    {"id": "A", "label": "A", "x": 80, "y": 90},
    {"id": "B", "label": "B", "x": 250, "y": 60},
    {"id": "C", "label": "C", "x": 430, "y": 120},
    {"id": "D", "label": "D", "x": 170, "y": 270},
    {"id": "E", "label": "E", "x": 380, "y": 300},
]

DEFAULT_EDGES = [
    {"id": "A-B", "source": "A", "target": "B", "cost": 4, "blocked": False},
    {"id": "A-C", "source": "A", "target": "C", "cost": 9, "blocked": False},
    {"id": "A-D", "source": "A", "target": "D", "cost": 7, "blocked": False},
    {"id": "B-C", "source": "B", "target": "C", "cost": 3, "blocked": False},
    {"id": "B-D", "source": "B", "target": "D", "cost": 6, "blocked": False},
    {"id": "B-E", "source": "B", "target": "E", "cost": 5, "blocked": False},
    {"id": "C-E", "source": "C", "target": "E", "cost": 4, "blocked": False},
    {"id": "D-E", "source": "D", "target": "E", "cost": 2, "blocked": False},
]

SCENARIOS = {
    "baseline": {},
    "single_block": {"B-E": {"blocked": True}},
    "cost_spike": {"A-C": {"cost": 20}},
    "infeasible": {
        "B-E": {"blocked": True},
        "C-E": {"blocked": True},
        "D-E": {"blocked": True},
    },
}


def seed_default_graph(session: Session) -> None:
    if session.exec(select(NodeRecord)).first() is not None:
        return

    session.add_all(NodeRecord.model_validate(node) for node in DEFAULT_NODES)
    session.add_all(EdgeRecord.model_validate(edge) for edge in DEFAULT_EDGES)
    session.commit()


def _serialize_graph(session: Session) -> GraphRead:
    nodes = session.exec(select(NodeRecord).order_by(NodeRecord.id)).all()
    edges = session.exec(select(EdgeRecord).order_by(EdgeRecord.id)).all()
    return GraphRead(
        nodes=[NodeRead.model_validate(node) for node in nodes],
        edges=[EdgeRead.model_validate(edge) for edge in edges],
    )


def get_graph(session: Session) -> GraphRead:
    seed_default_graph(session)
    return _serialize_graph(session)


def patch_edge(session: Session, edge_id: str, patch: EdgePatch) -> EdgeRead:
    edge = session.get(EdgeRecord, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="edge not found")

    if patch.cost is not None:
        edge.cost = patch.cost
    if patch.blocked is not None:
        edge.blocked = patch.blocked

    session.add(edge)
    session.commit()
    session.refresh(edge)
    return EdgeRead.model_validate(edge)


def reset_graph(session: Session) -> GraphRead:
    for edge in session.exec(select(EdgeRecord)).all():
        session.delete(edge)
    for node in session.exec(select(NodeRecord)).all():
        session.delete(node)
    session.commit()
    seed_default_graph(session)
    return _serialize_graph(session)


def load_scenario(session: Session, scenario_id: str) -> GraphRead:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail="scenario not found")

    reset_graph(session)
    for edge_id, change in SCENARIOS[scenario_id].items():
        patch_edge(session, edge_id, EdgePatch(**change))
    return _serialize_graph(session)
