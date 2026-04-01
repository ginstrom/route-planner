from sqlmodel import Session, select

from backend.models import RunRecord, TraceRead, TraceStepRecord


def create_run(session: Session, mode: str, request_payload: dict[str, object] | None = None) -> RunRecord:
    run = RunRecord(mode=mode, request_payload=request_payload)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_run(
    session: Session,
    run_id: str,
    status: str,
    result_payload: dict[str, object] | None = None,
    error_message: str | None = None,
) -> RunRecord:
    run = session.get(RunRecord, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    run.status = status
    if result_payload is not None:
        run.result_payload = result_payload
    if error_message is not None:
        run.error_message = error_message
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


class TraceHandle:
    def __init__(self, trace_id: str, run_id: str):
        self.id = trace_id
        self.run_id = run_id


def create_trace(session: Session, run_id: str) -> TraceHandle:
    return TraceHandle(trace_id=run_id, run_id=run_id)


def append_trace_step(
    session: Session,
    trace_id: str,
    step_type: str,
    name: str,
    summary: str,
    payload: dict[str, object],
    highlights: dict[str, object] | None = None,
    latency_ms: int | None = None,
) -> TraceStepRecord:
    existing_count = len(session.exec(select(TraceStepRecord).where(TraceStepRecord.trace_id == trace_id)).all())
    step = TraceStepRecord(
        trace_id=trace_id,
        run_id=trace_id,
        step_index=existing_count,
        step_type=step_type,
        name=name,
        summary=summary,
        payload=payload,
        highlights=highlights or {},
        latency_ms=latency_ms,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def fetch_trace(session: Session, trace_id: str) -> dict[str, object]:
    steps = session.exec(
        select(TraceStepRecord)
        .where(TraceStepRecord.trace_id == trace_id)
        .order_by(TraceStepRecord.step_index)
    ).all()
    run = session.get(RunRecord, trace_id)
    if run is None:
        raise ValueError(f"Trace {trace_id} not found")
    return TraceRead(
        trace_id=trace_id,
        run_id=run.id,
        steps=[
            {
                "step_index": step.step_index,
                "step_type": step.step_type,
                "name": step.name,
                "summary": step.summary,
                "payload": step.payload,
                "highlights": step.highlights,
                "latency_ms": step.latency_ms,
            }
            for step in steps
        ],
    ).model_dump()
