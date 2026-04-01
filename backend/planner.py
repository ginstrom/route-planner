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
    TraceExplainRequest,
    TraceExplainResponse,
    RunRecord,
)
from backend.solver import solve_route
from backend.trace import append_trace_step, create_run, create_trace, fetch_trace, update_run


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

ORCHESTRATION_TOOL_DEFINITIONS = [
    tool
    for tool in TOOL_DEFINITIONS
    if tool["name"] not in {"planner_verify_solution", "planner_explain_infeasibility"}
]

SYSTEM_PROMPT = """You are the planner orchestrator for an explainable route planner.
Use the provided tools to inspect the graph, parse the request, preview the problem, solve it,
inspect candidates, then stop after you have enough information for candidate selection or infeasibility handling.
Do not expose chain-of-thought. End after the relevant tools have been called."""

EXPLANATION_SYSTEM_PROMPT = """You explain route-planning decisions using the provided task prompt, final result, candidate summary, and stored trace.
Treat any route appearing in the candidate summary as having been evaluated by the solver—do not claim it was not considered.
Do not invent missing evidence. If none of the provided data justifies a claim, say so directly.
Do not expose chain-of-thought."""


class PlannerFailure(Exception):
    pass


@dataclass
class PlannerState:
    query: str
    graph: Any
    constraints: dict[str, object]
    parsed: DirectSolveRequest | None = None
    solved: DirectSolveResponse | None = None
    choice: dict[str, Any] | None = None
    verification: dict[str, object] | None = None


def _text_from_anthropic_blocks(blocks: list[Any]) -> str:
    lines = [getattr(block, "text", "").strip() for block in blocks if getattr(block, "type", "") == "text"]
    return "\n".join(line for line in lines if line).strip()


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

    cleaned = normalized
    for pattern in (
        r"(?:,\s*)?(?:BUT\s+)?DON'T VISIT\s+[A-Z]\b(?:\s+UNLESS THERE IS NO OTHER WAY)?",
        r"(?:,\s*)?(?:BUT\s+)?DO NOT VISIT\s+[A-Z]\b(?:\s+UNLESS THERE IS NO OTHER WAY)?",
        r"(?:,\s*)?(?:BUT\s+)?AVOID(?:\s+VISITING)?\s+[A-Z]\b(?:\s+IF POSSIBLE)?",
        r"(?:,\s*)?(?:BUT\s+)?PREFER NOT TO (?:GO THROUGH|VISIT)\s+[A-Z]\b",
    ):
        cleaned = re.sub(pattern, "", cleaned)

    mentions = [match for match in re.findall(r"\b([A-Z])\b", cleaned) if match in node_ids]
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


def _graph_edge_facts(graph) -> list[dict[str, Any]]:
    return [
        {
            "edge_id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "cost": edge.cost,
            "blocked": edge.blocked,
        }
        for edge in sorted(graph.edges, key=lambda item: item.id)
    ]


def _edge_lookup(graph_edge_facts: list[dict[str, Any]]) -> dict[frozenset[str], dict[str, Any]]:
    return {
        frozenset((str(edge["source"]), str(edge["target"]))): edge
        for edge in graph_edge_facts
    }


def _analyze_route_nodes(route: list[str], graph_edge_facts: list[dict[str, Any]]) -> dict[str, Any]:
    edge_lookup = _edge_lookup(graph_edge_facts)
    segments: list[dict[str, Any]] = []
    blocked_edges: list[str] = []
    missing_edges: list[str] = []
    total_cost = 0

    for source, target in zip(route, route[1:]):
        edge = edge_lookup.get(frozenset((source, target)))
        if edge is None:
            missing_edges.append(f"{source}-{target}")
            continue

        segment = {
            "edge_id": edge["edge_id"],
            "source": source,
            "target": target,
            "cost": edge["cost"],
            "blocked": edge["blocked"],
        }
        segments.append(segment)
        total_cost += int(edge["cost"])
        if edge["blocked"]:
            blocked_edges.append(str(edge["edge_id"]))

    return {
        "route": list(route),
        "segments": segments,
        "total_cost": total_cost if len(route) <= 1 or (not blocked_edges and not missing_edges and len(segments) == len(route) - 1) else None,
        "blocked_edges": blocked_edges,
        "missing_edges": missing_edges,
        "is_valid": not blocked_edges and not missing_edges and len(segments) == max(len(route) - 1, 0),
    }


def _build_solve_trace_payload(
    graph,
    request: DirectSolveRequest,
    solved: DirectSolveResponse,
) -> dict[str, Any]:
    graph_edge_facts = _graph_edge_facts(graph)
    candidate_routes = []
    for candidate in solved.candidates:
        candidate_payload = candidate.model_dump()
        candidate_payload["segments"] = _analyze_route_nodes(candidate.route, graph_edge_facts)["segments"] if candidate.route else []
        candidate_routes.append(candidate_payload)

    selected_route = _analyze_route_nodes(solved.route, graph_edge_facts) if solved.route else None

    return {
        "status": solved.status,
        "route": solved.route,
        "total_cost": solved.total_cost,
        "solver_input": request.model_dump(),
        "graph_edge_facts": graph_edge_facts,
        "selected_route": selected_route,
        "candidate_routes": candidate_routes,
        "infeasibility_reason": solved.infeasibility_reason,
    }


def _accepted_candidates(solved: DirectSolveResponse) -> list[dict[str, Any]]:
    return [candidate.model_dump() for candidate in solved.candidates if candidate.status == "ACCEPTED"]


def _fallback_candidate(solved: DirectSolveResponse) -> dict[str, Any]:
    accepted = _accepted_candidates(solved)
    if not accepted:
        raise PlannerFailure("No accepted candidates available for fallback selection.")
    return accepted[0]


def _has_soft_preference_language(query: str) -> bool:
    return bool(re.search(r"\b(avoid|prefer|unless|if possible|rather than|instead of|don't|do not)\b", query, re.IGNORECASE))


def _find_matching_candidate(
    candidates: list[dict[str, Any]],
    route: list[str] | None,
) -> dict[str, Any] | None:
    if not isinstance(route, list):
        return None
    for candidate in candidates:
        if candidate.get("route") == route:
            return candidate
    return None


def _apply_selected_candidate(state: PlannerState, selected_candidate: dict[str, Any]) -> None:
    if state.solved is None:
        raise PlannerFailure("No solve result available to update with selected candidate.")
    state.solved.route = list(selected_candidate.get("route", []))
    state.solved.total_cost = selected_candidate.get("total_cost")


def _record_candidate_choice(
    session: Session,
    trace_id: str,
    state: PlannerState,
    accepted_candidates: list[dict[str, Any]],
    selected_candidate: dict[str, Any],
    rationale: str,
    raw_decision: str,
    matched_solver_candidate: bool,
    used_fallback: bool,
) -> None:
    payload = {
        "query": state.query,
        "accepted_candidates": accepted_candidates,
        "selected_candidate": selected_candidate,
        "rationale": rationale,
        "raw_decision": raw_decision,
        "verification": {"matched_solver_candidate": matched_solver_candidate},
        "used_fallback": used_fallback,
    }
    state.choice = payload
    summary = "Selected a candidate route from the solver candidate list."
    if used_fallback:
        summary = "Candidate selection fell back to the deterministic solver choice."
    append_trace_step(session, trace_id, "planner", "planner.choose_candidate", summary, payload)


def _build_candidate_selection_query(query: str, accepted_candidates: list[dict[str, Any]]) -> dict[str, str]:
    user_prompt = (
        f"User query:\n{query}\n\n"
        f"Accepted solver candidates:\n{json.dumps(accepted_candidates, indent=2)}\n\n"
        "Choose exactly one candidate from the accepted solver candidates.\n"
        'Respond with JSON in the form {"route":["A","B"],"rationale":"..."}.\n'
        "The route must exactly match one candidate route from the provided list.\n"
        "Default decision rule: choose the candidate with the lowest total cost that satisfies the hard requirements.\n"
        "Only choose a higher-cost candidate when the user explicitly asks for a soft tradeoff or preference, such as avoid, prefer, unless, or if possible.\n"
        "If no such soft preference is stated, lowest total cost wins.\n"
    )
    return {
        "system_prompt": "You select the best route candidate from a provided solver-generated list. Return only valid JSON.",
        "user_prompt": user_prompt,
    }


def _parse_candidate_selection_response(text: str) -> tuple[list[str] | None, str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerFailure(f"Candidate choice response was not valid JSON: {exc.msg}") from exc
    route = payload.get("route")
    rationale = str(payload.get("rationale", "")).strip()
    if not isinstance(route, list) or not all(isinstance(node, str) for node in route):
        raise PlannerFailure("Candidate choice response did not include a valid route list.")
    return route, rationale


def _choose_candidate(
    session: Session,
    trace_id: str,
    state: PlannerState,
    settings: Settings,
    client: Anthropic | None = None,
) -> None:
    if state.solved is None:
        raise PlannerFailure("Candidate selection requires a solve result.")

    accepted_candidates = _accepted_candidates(state.solved)
    if not accepted_candidates:
        raise PlannerFailure("Candidate selection requires at least one accepted candidate.")

    if settings.planner_mode == "local":
        selected_candidate = _fallback_candidate(state.solved)
        _apply_selected_candidate(state, selected_candidate)
        _record_candidate_choice(
            session,
            trace_id,
            state,
            accepted_candidates,
            selected_candidate,
            "Local mode uses deterministic candidate selection.",
            raw_decision="",
            matched_solver_candidate=True,
            used_fallback=True,
        )
        return

    if client is None:
        client = get_anthropic_client(settings)

    llm_query = _build_candidate_selection_query(state.query, accepted_candidates)
    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            system=[{"type": "text", "text": llm_query["system_prompt"], "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": llm_query["user_prompt"]}],
        )
        raw_decision = _text_from_anthropic_blocks(list(getattr(response, "content", [])))
        if not raw_decision:
            raise PlannerFailure("Candidate choice response was empty.")
        selected_route, rationale = _parse_candidate_selection_response(raw_decision)
        matched_candidate = _find_matching_candidate(accepted_candidates, selected_route)
        if matched_candidate is None:
            raise PlannerFailure("Candidate choice route did not match an accepted solver candidate.")
        used_fallback = False
        if not _has_soft_preference_language(state.query):
            cheapest_candidate = min(
                accepted_candidates,
                key=lambda candidate: (candidate.get("total_cost") or 0, candidate.get("route") or []),
            )
            if matched_candidate.get("route") != cheapest_candidate.get("route"):
                matched_candidate = cheapest_candidate
                rationale = "Overrode LLM choice to the lowest-cost candidate because the query did not express a soft preference."
                used_fallback = True
        _apply_selected_candidate(state, matched_candidate)
        _record_candidate_choice(
            session,
            trace_id,
            state,
            accepted_candidates,
            matched_candidate,
            rationale,
            raw_decision=raw_decision,
            matched_solver_candidate=True,
            used_fallback=used_fallback,
        )
    except PlannerFailure:
        if settings.planner_mode != "anthropic_with_fallback":
            raise
        selected_candidate = _fallback_candidate(state.solved)
        _apply_selected_candidate(state, selected_candidate)
        _record_candidate_choice(
            session,
            trace_id,
            state,
            accepted_candidates,
            selected_candidate,
            "Candidate choice failed; used deterministic fallback.",
            raw_decision=locals().get("raw_decision", ""),
            matched_solver_candidate=False,
            used_fallback=True,
        )
    except Exception as exc:
        if settings.planner_mode != "anthropic_with_fallback":
            raise PlannerFailure(str(exc)) from exc
        selected_candidate = _fallback_candidate(state.solved)
        _apply_selected_candidate(state, selected_candidate)
        _record_candidate_choice(
            session,
            trace_id,
            state,
            accepted_candidates,
            selected_candidate,
            f"Candidate choice failed; used deterministic fallback: {exc}",
            raw_decision="",
            matched_solver_candidate=False,
            used_fallback=True,
        )


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
        payload = _build_solve_trace_payload(state.graph, state.parsed, state.solved)
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
        _choose_candidate(session, trace_id, state, get_settings())
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


def _build_local_explanation(
    task_prompt: str,
    question: str,
    run: RunRecord,
    trace_payload: dict[str, object],
    used_fallback: bool = False,
) -> str:
    result_payload = run.result_payload or {}
    route = result_payload.get("route")
    route_text = " -> ".join(route) if isinstance(route, list) and route else "no final route"
    steps = trace_payload.get("steps", [])
    verify_step = next((step for step in steps if step.get("name") == "planner.verify_solution"), None) if isinstance(steps, list) else None
    infeasible_step = next((step for step in steps if step.get("name") == "planner.explain_infeasibility"), None) if isinstance(steps, list) else None
    candidate_step = next((step for step in steps if step.get("name") == "planner.get_candidates"), None) if isinstance(steps, list) else None
    solve_step = next((step for step in steps if step.get("name") == "planner.solve"), None) if isinstance(steps, list) else None
    solve_payload = solve_step.get("payload", {}) if isinstance(solve_step, dict) else {}
    fallback_prefix = (
        "Anthropic explanation failed; showing fallback explanation grounded in trace data. "
        if used_fallback
        else ""
    )

    parts = [fallback_prefix + f"The planner chose {route_text}."]
    if task_prompt:
        parts.append(f"Task prompt: {task_prompt}.")
    if isinstance(verify_step, dict):
        parts.append(f"Verification step: {verify_step.get('summary', '')}")
    elif isinstance(infeasible_step, dict):
        parts.append(f"Infeasibility trace: {infeasible_step.get('summary', '')}")

    candidate_payload = candidate_step.get("payload", {}) if isinstance(candidate_step, dict) else {}
    candidates = candidate_payload.get("candidates", []) if isinstance(candidate_payload, dict) else []
    chosen_route_nodes = route if isinstance(route, list) else []
    route_mentions = _parse_route_mentions(question)
    chosen_mention = next((mention for mention in route_mentions if chosen_route_nodes[: len(mention)] == mention), None)
    alternative_route = next((mention for mention in route_mentions if mention != chosen_mention), None)
    if alternative_route is None and route_mentions and chosen_mention is None:
        alternative_route = route_mentions[0]

    if alternative_route and isinstance(solve_payload, dict):
        alternative_analysis = _analyze_route_nodes(alternative_route, solve_payload.get("graph_edge_facts", []))
        if alternative_analysis["blocked_edges"]:
            blocked_edges = ", ".join(alternative_analysis["blocked_edges"])
            parts.append(
                f"The named alternative {_compact_route(alternative_route)} was not available because it uses blocked edge {blocked_edges}."
            )
        elif alternative_analysis["missing_edges"]:
            missing_edges = ", ".join(alternative_analysis["missing_edges"])
            parts.append(
                f"The named alternative {_compact_route(alternative_route)} is not a valid path in the graph because edge {missing_edges} does not exist."
            )
        elif alternative_analysis["is_valid"] and isinstance(candidates, list):
            chosen_candidate = _prefix_match_candidate(candidates, chosen_route_nodes)
            compared_candidate = _prefix_match_candidate(candidates, alternative_route)
            if chosen_candidate and compared_candidate:
                chosen_cost = chosen_candidate.get("total_cost")
                alternative_cost = compared_candidate.get("total_cost")
                compared_route = " -> ".join(compared_candidate.get("route", []))
                if chosen_cost is not None and alternative_cost is not None:
                    parts.append(
                        f"The candidate list includes {route_text} at cost {chosen_cost} and {compared_route} at cost {alternative_cost}, so the planner selected the lower-cost valid route."
                    )
                else:
                    parts.append(f"The candidate list includes the alternative route {compared_route}, but it was not selected.")
            else:
                parts.append(
                    f"The named alternative {_compact_route(alternative_route)} is a valid path with total cost {alternative_analysis['total_cost']}, but it does not appear in the candidate summary closely enough to compare directly."
                )
    elif isinstance(candidates, list):
        chosen_candidate = _prefix_match_candidate(candidates, chosen_route_nodes)
        compared_candidate = _prefix_match_candidate(candidates, alternative_route) if alternative_route else None
        if chosen_candidate and compared_candidate:
            chosen_cost = chosen_candidate.get("total_cost")
            alternative_cost = compared_candidate.get("total_cost")
            compared_route = " -> ".join(compared_candidate.get("route", []))
            if chosen_cost is not None and alternative_cost is not None:
                parts.append(
                    f"The candidate list includes {route_text} at cost {chosen_cost} and {compared_route} at cost {alternative_cost}, so the planner selected the lower-cost valid route."
                )
            else:
                parts.append(f"The candidate list includes the alternative route {compared_route}, but it was not selected.")
        elif route_mentions:
            parts.append("The candidate list does not contain a route that matches the named alternative closely enough to compare it directly.")
        else:
            parts.append(f"Question asked: {question}")
    else:
        parts.append(f"Question asked: {question}")

    return " ".join(part.strip() for part in parts if part).strip()


def _extract_candidate_payload(run: RunRecord, trace_payload: dict[str, object]) -> dict[str, object]:
    steps = trace_payload.get("steps", [])
    candidate_step = next((step for step in steps if step.get("name") == "planner.get_candidates"), None) if isinstance(steps, list) else None
    if isinstance(candidate_step, dict):
        payload = candidate_step.get("payload", {})
        if isinstance(payload, dict) and payload.get("candidates"):
            return payload
    result_payload = run.result_payload or {}
    result_candidates = result_payload.get("candidates") if isinstance(result_payload, dict) else None
    if isinstance(result_candidates, list):
        return {"candidates": result_candidates}
    return {}


def _parse_route_mentions(question: str) -> list[list[str]]:
    matches = re.findall(r"[A-Z](?:\s*(?:->|-)\s*[A-Z])+", question.upper())
    return [re.findall(r"[A-Z]", match) for match in matches]


def _compact_route(route: list[str]) -> str:
    return "-".join(route)


def _prefix_match_candidate(candidates: list[dict[str, Any]], nodes: list[str] | None) -> dict[str, Any] | None:
    if not nodes:
        return None
    for candidate in candidates:
        route_nodes = candidate.get("route")
        if isinstance(route_nodes, list) and route_nodes[: len(nodes)] == nodes:
            return candidate
    return None


def _build_compared_candidates_section(question: str, run: RunRecord, candidate_payload: dict[str, object]) -> str:
    candidates = candidate_payload.get("candidates", []) if isinstance(candidate_payload, dict) else []
    if not isinstance(candidates, list):
        return "{}"

    chosen_route = run.result_payload.get("route") if isinstance(run.result_payload, dict) else None
    route_mentions = _parse_route_mentions(question)
    alternative_nodes = route_mentions[1] if len(route_mentions) > 1 else (route_mentions[0] if route_mentions else None)

    return json.dumps(
        {
            "chosen_route": _prefix_match_candidate(candidates, chosen_route if isinstance(chosen_route, list) else None),
            "alternative_route": _prefix_match_candidate(candidates, alternative_nodes),
        },
        indent=2,
    )


def _build_llm_query(task_prompt: str, question: str, run: RunRecord, trace_payload: dict[str, object]) -> dict[str, str]:
    result_payload = json.dumps(run.result_payload or {}, indent=2)
    steps = trace_payload.get("steps", [])
    candidate_payload = _extract_candidate_payload(run, trace_payload)
    candidate_summary = json.dumps(candidate_payload, indent=2)
    solve_step = next((step for step in steps if step.get("name") == "planner.solve"), None) if isinstance(steps, list) else None
    solve_facts = json.dumps(solve_step.get("payload", {}) if isinstance(solve_step, dict) else {}, indent=2)
    compared_candidates = _build_compared_candidates_section(question, run, candidate_payload)
    trace_json = json.dumps(steps, indent=2)
    user_prompt = (
        f"Task prompt:\n{task_prompt or '(missing)'}\n\n"
        f"Final run status: {run.status}\n"
        f"Final result payload:\n{result_payload}\n\n"
        f"Solve route facts:\n{solve_facts}\n\n"
        f"Candidate summary from trace:\n{candidate_summary}\n\n"
        f"Compared candidate routes:\n{compared_candidates}\n\n"
        f"Stored trace steps:\n{trace_json}\n\n"
        f"User question:\n{question}\n\n"
        "When the user names partial routes such as A-B-C instead of full routes, compare against the closest full candidate by matching that prefix.\n"
        "If a named alternative is present in the candidate summary, explicitly compare its cost/status against the chosen route.\n"
        "If a named alternative is not a candidate route, use Solve route facts to determine whether it traverses blocked or missing edges before answering.\n"
        "Do not say the alternative was not considered if it appears in either Candidate summary from trace or Compared candidate routes.\n"
    )
    return {"system_prompt": EXPLANATION_SYSTEM_PROMPT, "user_prompt": user_prompt}


def _run_anthropic_explanation(
    task_prompt: str,
    question: str,
    run: RunRecord,
    trace_payload: dict[str, object],
    settings: Settings,
) -> str:
    client = get_anthropic_client(settings)
    llm_query = _build_llm_query(task_prompt, question, run, trace_payload)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=400,
        system=[{"type": "text", "text": llm_query["system_prompt"], "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": llm_query["user_prompt"]}],
    )
    answer = _text_from_anthropic_blocks(list(getattr(response, "content", [])))
    if not answer:
        raise PlannerFailure("Anthropic explanation response was empty.")
    return answer


def explain_trace(session: Session, trace_id: str, request: TraceExplainRequest) -> TraceExplainResponse:
    question = request.question.strip()
    if not question:
        raise ValueError("Explanation question must not be blank.")

    run = session.get(RunRecord, trace_id)
    if run is None:
        raise ValueError(f"Trace {trace_id} not found")
    if run.result_payload is None and run.status == "PENDING":
        raise ValueError("Trace explanation requires a completed planner run.")

    trace_payload = fetch_trace(session, trace_id)
    task_prompt = request.task_prompt or ((run.request_payload or {}).get("query") if isinstance(run.request_payload, dict) else None) or ""
    settings = get_settings()
    llm_query = _build_llm_query(task_prompt, question, run, trace_payload)

    if settings.planner_mode == "local":
        return TraceExplainResponse(
            trace_id=trace_id,
            planner_mode=settings.planner_mode,
            used_fallback=False,
            answer=_build_local_explanation(task_prompt, question, run, trace_payload),
            llm_query=llm_query,
        )

    if settings.planner_mode == "anthropic":
        return TraceExplainResponse(
            trace_id=trace_id,
            planner_mode=settings.planner_mode,
            used_fallback=False,
            answer=_run_anthropic_explanation(task_prompt, question, run, trace_payload, settings),
            llm_query=llm_query,
        )

    if settings.planner_mode == "anthropic_with_fallback":
        try:
            answer = _run_anthropic_explanation(task_prompt, question, run, trace_payload, settings)
            used_fallback = False
        except Exception:
            answer = _build_local_explanation(task_prompt, question, run, trace_payload, used_fallback=True)
            used_fallback = True
        return TraceExplainResponse(
            trace_id=trace_id,
            planner_mode=settings.planner_mode,
            used_fallback=used_fallback,
            answer=answer,
            llm_query=llm_query,
        )

    raise PlannerFailure(f"Unsupported planner mode: {settings.planner_mode}")


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
                tools=ORCHESTRATION_TOOL_DEFINITIONS,
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

    if state.solved is None:
        raise PlannerFailure("Anthropic did not produce a solved planner state.")
    if state.solved.status == "SUCCESS":
        _choose_candidate(session, trace_id, state, settings, client=client)
        _execute_tool(session, trace_id, state, "planner.verify_solution", {})
    else:
        _execute_tool(session, trace_id, state, "planner.explain_infeasibility", {})


def plan_route(session: Session, request: PlanRequest) -> PlanResponse:
    settings = get_settings()
    run = create_run(session, mode="planner", request_payload={"query": request.query})
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
            result_payload={
                "route": state.solved.route,
                "total_cost": state.solved.total_cost,
                "candidates": [candidate.model_dump() for candidate in state.solved.candidates],
            },
        )
    elif state.solved and state.solved.status == "INFEASIBLE":
        update_run(
            session,
            run.id,
            status="INFEASIBLE",
            result_payload={
                "reason": state.solved.infeasibility_reason,
                "candidates": [candidate.model_dump() for candidate in state.solved.candidates],
            },
        )

    return _build_plan_response(run.id, trace.id, state)
