import json
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from anthropic import Anthropic
from sqlmodel import Session

from backend.config import Settings, get_settings
from backend.graph import DEFAULT_EDGES, get_graph
from backend.models import (
    DirectSolveRequest,
    DirectSolveResponse,
    PlanRequest,
    PlanResponse,
)
from backend.solver import solve_route
from backend.trace import append_trace_step, create_run, create_trace, update_run


TOOL_NAME_ALIASES = {
    "graph_get_state": "graph.get_state",
    "scenario_get_constraints": "scenario.get_constraints",
    "parse_request": "parse_request",
    "planner_preview_problem": "planner.preview_problem",
    "planner_solve": "planner.solve",
    "planner_get_candidates": "planner.get_candidates",
    "planner_verify_solution": "planner.verify_solution",
    "planner_explain_infeasibility": "planner.explain_infeasibility",
}

TOOL_DEFINITIONS = [
    {
        "name": "graph_get_state",
        "description": "Return the current graph nodes and edges.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "scenario_get_constraints",
        "description": "Return blocked edges and modified costs relative to the default graph.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "parse_request",
        "description": "Parse a natural-language routing request into a formal route request.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "planner_preview_problem",
        "description": "Preview the formal routing problem after parsing.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "planner_solve",
        "description": "Solve the current formal routing problem.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "planner_get_candidates",
        "description": "Return the candidate routes for the last solve.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "planner_verify_solution",
        "description": "Verify the selected route satisfies the request.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "planner_explain_infeasibility",
        "description": "Explain why the current request is infeasible.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

SYSTEM_PROMPT = """You are the planner orchestrator for an explainable route planner.
Use the provided tools to inspect the graph, parse the request, preview the problem, solve it,
inspect candidates, and either verify the solution or explain infeasibility.
Do not expose chain-of-thought. End after the relevant tools have been called."""


class PlannerFailure(Exception):
    pass


@dataclass
class PlannerState:
    query: str
    graph: Any
    constraints: dict[str, object]
    parsed: DirectSolveRequest | None = None
    solved: DirectSolveResponse | None = None
    verification: dict[str, object] | None = None


def get_anthropic_client(settings: Settings) -> Anthropic:
    if not settings.anthropic_api_key:
        raise PlannerFailure("ANTHROPIC_API_KEY is required for planner_mode=anthropic.")
    return Anthropic(api_key=settings.anthropic_api_key)


def _scenario_constraints(graph) -> dict[str, object]:
    default_by_id = {edge["id"]: edge for edge in DEFAULT_EDGES}
    blocked_edges = [edge.id for edge in graph.edges if edge.blocked]
    modified_costs = {
        edge.id: edge.cost
        for edge in graph.edges
        if edge.cost != default_by_id[edge.id]["cost"]
    }
    return {"blocked_edges": blocked_edges, "modified_costs": modified_costs}


def _parse_request(query: str, node_ids: set[str]) -> DirectSolveRequest:
    normalized = query.upper()
    start_match = re.search(r"(?:START AT|FROM)\s+([A-Z])\b", normalized)
    if start_match is None:
        raise PlannerFailure("Could not determine a start node from the request.")
    start_node = start_match.group(1)
    if start_node not in node_ids:
        raise PlannerFailure(f"Unknown start node {start_node}.")

    mentions = [match for match in re.findall(r"\b([A-Z])\b", normalized) if match in node_ids]
    required_visits: list[str] = []
    for node_id in mentions:
        if node_id != start_node and node_id not in required_visits:
            required_visits.append(node_id)

    return DirectSolveRequest(
        start_node=start_node,
        required_visits=required_visits,
        return_to_start="RETURN" in normalized and "START" in normalized,
    )


def _verify_solution(result: DirectSolveResponse, request: DirectSolveRequest) -> dict[str, object]:
    if result.status != "SUCCESS":
        return {"verified": False, "reason": "No successful route to verify."}
    route_set = set(result.route)
    missing = [node for node in request.required_visits if node not in route_set]
    if missing:
        return {"verified": False, "reason": f"Missing required visits: {missing}"}
    return {"verified": True, "reason": "Route satisfies the requested visits."}


def _canonicalize_tool_name(name: str) -> str:
    return TOOL_NAME_ALIASES.get(name, name)


def _execute_tool(session: Session, trace_id: str, state: PlannerState, name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    name = _canonicalize_tool_name(name)

    if name == "graph.get_state":
        payload = state.graph.model_dump()
        append_trace_step(session, trace_id, "tool", name, "Loaded the current graph state.", payload)
        return payload

    if name == "scenario.get_constraints":
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            "Collected blocked edges and modified costs.",
            state.constraints,
        )
        return state.constraints

    if name == "parse_request":
        query = str(tool_input.get("query", state.query))
        try:
            state.parsed = _parse_request(query, {node.id for node in state.graph.nodes})
        except PlannerFailure as exc:
            append_trace_step(
                session,
                trace_id,
                "tool",
                name,
                str(exc),
                {"query": query},
            )
            raise
        payload = state.parsed.model_dump()
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            "Parsed the natural-language request into a formal route request.",
            payload,
        )
        return payload

    if name == "planner.preview_problem":
        if state.parsed is None:
            raise PlannerFailure("planner.preview_problem requires a parsed request.")
        payload = state.parsed.model_dump()
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            "Prepared the formal routing problem for solving.",
            payload,
        )
        return payload

    if name == "planner.solve":
        if state.parsed is None:
            raise PlannerFailure("planner.solve requires a parsed request.")
        state.solved = solve_route(state.graph, state.parsed)
        payload = {"status": state.solved.status, "route": state.solved.route, "total_cost": state.solved.total_cost}
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            f"Computed a {state.solved.status.lower()} solve result.",
            payload,
        )
        return payload

    if name == "planner.get_candidates":
        if state.solved is None:
            raise PlannerFailure("planner.get_candidates requires a solve result.")
        payload = {"candidates": [candidate.model_dump() for candidate in state.solved.candidates]}
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            "Retrieved candidate route options from the deterministic solver.",
            payload,
        )
        return payload

    if name == "planner.verify_solution":
        if state.solved is None or state.parsed is None:
            raise PlannerFailure("planner.verify_solution requires a solved request.")
        state.verification = _verify_solution(state.solved, state.parsed)
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            str(state.verification["reason"]),
            state.verification,
        )
        return state.verification

    if name == "planner.explain_infeasibility":
        if state.solved is None:
            raise PlannerFailure("planner.explain_infeasibility requires a solve result.")
        explanation = state.solved.infeasibility_reason or "No feasible route found."
        payload = {"reason": explanation}
        append_trace_step(
            session,
            trace_id,
            "tool",
            name,
            explanation,
            payload,
        )
        return payload

    raise PlannerFailure(f"Unsupported tool requested: {name}")


def _build_plan_response(run_id: str, trace_id: str, state: PlannerState, failure_summary: str | None = None) -> PlanResponse:
    if state.solved and state.solved.status == "SUCCESS":
        summary = f"Planned route {' -> '.join(state.solved.route)} with total cost {state.solved.total_cost}."
        return PlanResponse(
            run_id=run_id,
            trace_id=trace_id,
            status="SUCCESS",
            route=state.solved.route,
            total_cost=state.solved.total_cost,
            candidates=state.solved.candidates,
            summary=summary,
        )

    if state.solved and state.solved.status == "INFEASIBLE":
        summary = state.solved.infeasibility_reason or "No feasible route found."
        return PlanResponse(
            run_id=run_id,
            trace_id=trace_id,
            status="INFEASIBLE",
            route=[],
            total_cost=None,
            candidates=state.solved.candidates,
            summary=summary,
        )

    return PlanResponse(
        run_id=run_id,
        trace_id=trace_id,
        status="FAILED",
        route=[],
        total_cost=None,
        candidates=[],
        summary=failure_summary or "Planner execution failed.",
    )


def _run_local_orchestration(session: Session, trace_id: str, state: PlannerState) -> None:
    sequence = [
        ("graph.get_state", {}),
        ("scenario.get_constraints", {}),
        ("parse_request", {"query": state.query}),
        ("planner.preview_problem", {}),
        ("planner.solve", {}),
        ("planner.get_candidates", {}),
    ]

    for name, tool_input in sequence:
        _execute_tool(session, trace_id, state, name, tool_input)

    if state.solved is None:
        raise PlannerFailure("Local planner did not produce a solve result.")

    if state.solved.status == "SUCCESS":
        _execute_tool(session, trace_id, state, "planner.verify_solution", {})
    else:
        _execute_tool(session, trace_id, state, "planner.explain_infeasibility", {})


def _assistant_message_content(blocks: list[Any]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for block in blocks:
        block_type = getattr(block, "type", "")
        if block_type == "tool_use":
            name = getattr(block, "name")
            serialized.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id"),
                    "name": name,
                    "input": getattr(block, "input", {}),
                }
            )
        elif block_type == "text":
            serialized.append({"type": "text", "text": getattr(block, "text", "")})
    return serialized


def _run_anthropic_orchestration(
    session: Session,
    trace_id: str,
    state: PlannerState,
    settings: Settings,
) -> None:
    client = get_anthropic_client(settings)
    messages: list[dict[str, Any]] = [{"role": "user", "content": state.query}]

    for _ in range(6):
        try:
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=800,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )
        except Exception as exc:
            raise PlannerFailure(str(exc)) from exc
        blocks = list(getattr(response, "content", []))
        tool_uses = [block for block in blocks if getattr(block, "type", "") == "tool_use"]
        if not tool_uses:
            break

        append_trace_step(
            session,
            trace_id,
            "planner",
            "planner.llm_turn",
            "Anthropic requested tool calls.",
            {"tools": [_canonicalize_tool_name(getattr(block, "name", "")) for block in tool_uses]},
        )
        messages.append({"role": "assistant", "content": _assistant_message_content(blocks)})

        tool_results = []
        for block in tool_uses:
            output = _execute_tool(session, trace_id, state, getattr(block, "name"), getattr(block, "input", {}) or {})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": getattr(block, "id"),
                    "content": json.dumps(output),
                }
            )
        messages.append({"role": "user", "content": tool_results})

        if state.solved and state.solved.status in {"SUCCESS", "INFEASIBLE"} and any(
            _canonicalize_tool_name(getattr(block, "name", "")) in {"planner.verify_solution", "planner.explain_infeasibility"}
            for block in tool_uses
        ):
            return

    if state.solved is None:
        raise PlannerFailure("Anthropic did not produce a solved planner state.")


def plan_route(session: Session, request: PlanRequest) -> PlanResponse:
    settings = get_settings()
    run = create_run(session, mode="planner")
    trace = create_trace(session, run_id=run.id)
    graph = get_graph(session)
    state = PlannerState(
        query=request.query,
        graph=graph,
        constraints=_scenario_constraints(graph),
    )

    if settings.planner_mode != "local":
        append_trace_step(
            session,
            trace.id,
            "planner",
            "planner.mode",
            f"Planner mode: {settings.planner_mode}",
            {"planner_mode": settings.planner_mode, "anthropic_model": settings.anthropic_model},
        )

    try:
        if settings.planner_mode == "local":
            _run_local_orchestration(session, trace.id, state)
        elif settings.planner_mode == "anthropic":
            _run_anthropic_orchestration(session, trace.id, state, settings)
        elif settings.planner_mode == "anthropic_with_fallback":
            try:
                _run_anthropic_orchestration(session, trace.id, state, settings)
            except Exception as exc:
                append_trace_step(
                    session,
                    trace.id,
                    "planner",
                    "planner.fallback",
                    f"Anthropic failed, falling back to local orchestration: {exc}",
                    {"error": str(exc)},
                )
                state = PlannerState(
                    query=request.query,
                    graph=graph,
                    constraints=_scenario_constraints(graph),
                )
                _run_local_orchestration(session, trace.id, state)
        else:
            raise PlannerFailure(f"Unsupported planner mode: {settings.planner_mode}")
    except PlannerFailure as exc:
        if settings.planner_mode == "anthropic":
            append_trace_step(
                session,
                trace.id,
                "planner",
                "planner.llm_error",
                str(exc),
                {"error": str(exc)},
            )
        update_run(session, run.id, status="FAILED", error_message=str(exc))
        return _build_plan_response(run.id, trace.id, state, failure_summary=str(exc))

    if state.solved and state.solved.status == "SUCCESS":
        update_run(
            session,
            run.id,
            status="SUCCESS",
            result_payload={"route": state.solved.route, "total_cost": state.solved.total_cost},
        )
    elif state.solved and state.solved.status == "INFEASIBLE":
        update_run(
            session,
            run.id,
            status="INFEASIBLE",
            result_payload={"reason": state.solved.infeasibility_reason},
        )

    return _build_plan_response(run.id, trace.id, state)
