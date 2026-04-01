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


def _enumerate_simple_candidates(graph: GraphRead, request: DirectSolveRequest) -> list[CandidateRoute]:
    adjacency = _adjacency(graph)
    required = set(request.required_visits)
    candidates: list[CandidateRoute] = []
    seen_routes: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str], cost: int, visited: set[str]) -> None:
        covered = required.issubset(path)
        if covered and (not request.return_to_start or (node == request.start_node and len(path) > 1)):
            route_key = tuple(path)
            if route_key not in seen_routes:
                seen_routes.add(route_key)
                candidates.append(
                    CandidateRoute(
                        route=list(path),
                        total_cost=cost,
                        status="ACCEPTED",
                        rejection_reason=None,
                    )
                )
            if not request.return_to_start:
                return

        for neighbor, edge_cost in adjacency.get(node, []):
            allow_return_to_start = (
                request.return_to_start
                and covered
                and neighbor == request.start_node
                and node != request.start_node
            )
            if neighbor in visited and not allow_return_to_start:
                continue

            next_path = path + [neighbor]
            if allow_return_to_start:
                dfs(neighbor, next_path, cost + edge_cost, visited)
            else:
                dfs(neighbor, next_path, cost + edge_cost, visited | {neighbor})

    dfs(request.start_node, [request.start_node], 0, {request.start_node})
    return sorted(candidates, key=lambda item: (item.total_cost or 0, item.route))


def _enumerate_rejected_candidates(graph: GraphRead, request: DirectSolveRequest) -> list[CandidateRoute]:
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

    rejected = sorted(
        (candidate for candidate in candidates if candidate.status == "REJECTED"),
        key=lambda item: item.rejection_reason or "",
    )
    return rejected


def _visited_avoid_nodes(route: list[str], request: DirectSolveRequest) -> list[str]:
    avoid_nodes = set(request.avoid_nodes) - set(request.required_visits)
    return [node for node in request.avoid_nodes if node in avoid_nodes and node in route]


def _candidate_rank(candidate: CandidateRoute, request: DirectSolveRequest) -> tuple[int, int, list[str]]:
    violations = len(_visited_avoid_nodes(candidate.route, request))
    return (violations, candidate.total_cost or 0, candidate.route)


def solve_route(graph: GraphRead, request: DirectSolveRequest) -> DirectSolveResponse:
    accepted = _enumerate_simple_candidates(graph, request)
    rejected = _enumerate_rejected_candidates(graph, request) if not accepted else []
    ordered_candidates = accepted + rejected

    if accepted:
        best = min(accepted, key=lambda candidate: _candidate_rank(candidate, request))
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
