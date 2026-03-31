from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import permutations

from backend.models import (
    CandidateRoute,
    DirectSolveRequest,
    DirectSolveResponse,
    GraphRead,
)


@dataclass(frozen=True)
class Segment:
    nodes: list[str]
    cost: int


def _adjacency(graph: GraphRead) -> dict[str, list[tuple[str, int]]]:
    adjacency = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        if edge.blocked:
            continue
        adjacency[edge.source].append((edge.target, edge.cost))
        adjacency[edge.target].append((edge.source, edge.cost))
    for neighbors in adjacency.values():
        neighbors.sort()
    return adjacency


def _shortest_path(
    adjacency: dict[str, list[tuple[str, int]]],
    start: str,
    goal: str,
) -> Segment | None:
    if start == goal:
        return Segment(nodes=[start], cost=0)

    queue: list[tuple[int, tuple[str, ...], str]] = [(0, (start,), start)]
    best: dict[str, int] = {start: 0}

    while queue:
        cost, path, node = heappop(queue)
        if node == goal:
            return Segment(nodes=list(path), cost=cost)
        if cost > best.get(node, cost):
            continue
        for neighbor, edge_cost in adjacency.get(node, []):
            next_cost = cost + edge_cost
            if next_cost < best.get(neighbor, next_cost + 1):
                best[neighbor] = next_cost
                heappush(queue, (next_cost, path + (neighbor,), neighbor))
    return None


def solve_route(graph: GraphRead, request: DirectSolveRequest) -> DirectSolveResponse:
    adjacency = _adjacency(graph)
    required = tuple(request.required_visits)
    visit_orders = list(permutations(required)) or [()]
    candidates: list[CandidateRoute] = []

    for visit_order in visit_orders:
        route = [request.start_node]
        total_cost = 0
        current = request.start_node
        rejected_reason: str | None = None
        targets = list(visit_order)
        if request.return_to_start:
            targets.append(request.start_node)

        for target in targets:
            segment = _shortest_path(adjacency, current, target)
            if segment is None:
                rejected_reason = f"{target} is not reachable from {current}"
                break
            route.extend(segment.nodes[1:])
            total_cost += segment.cost
            current = target

        candidates.append(
            CandidateRoute(
                route=route if rejected_reason is None else [],
                total_cost=total_cost if rejected_reason is None else None,
                status="REJECTED" if rejected_reason else "ACCEPTED",
                rejection_reason=rejected_reason,
            )
        )

    accepted = sorted(
        (candidate for candidate in candidates if candidate.status == "ACCEPTED"),
        key=lambda item: (item.total_cost or 0, item.route),
    )
    rejected = sorted(
        (candidate for candidate in candidates if candidate.status == "REJECTED"),
        key=lambda item: item.rejection_reason or "",
    )
    ordered_candidates = accepted + rejected

    if accepted:
        best = accepted[0]
        return DirectSolveResponse(
            status="SUCCESS",
            route=best.route,
            total_cost=best.total_cost,
            candidates=ordered_candidates,
            infeasibility_reason=None,
        )

    return DirectSolveResponse(
        status="INFEASIBLE",
        route=[],
        total_cost=None,
        candidates=ordered_candidates,
        infeasibility_reason=rejected[0].rejection_reason if rejected else "No feasible route found",
    )
