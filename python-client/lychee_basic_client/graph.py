import heapq
from collections import defaultdict, deque
from typing import Any, Optional

ROUTE_COST_PER_UNIT = {
    "ROAD": 1380,
    "WATER": 1250,
    "MOUNTAIN": 1780,
    "BRANCH": 1550,
}


def _edge_endpoints(edge: dict[str, Any]) -> Optional[tuple[str, str]]:
    start = edge.get("fromNodeId") or edge.get("fromNode")
    end = edge.get("toNodeId") or edge.get("toNode")
    if not start or not end:
        return None
    return start, end


def edge_weight(edge: dict[str, Any]) -> int:
    distance = edge.get("distance", 0)
    route_type = edge.get("routeType", "ROAD")
    return int(distance * ROUTE_COST_PER_UNIT.get(route_type, 1550))


def build_adjacency(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        endpoints = _edge_endpoints(edge)
        if endpoints is None:
            continue
        start, end = endpoints
        adjacency[start].add(end)
        if edge.get("bidirectional", True):
            adjacency[end].add(start)
    return {node: sorted(neighbors) for node, neighbors in adjacency.items()}


def build_weighted_adjacency(edges: list[dict[str, Any]]) -> dict[str, list[tuple[str, int]]]:
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for edge in edges:
        endpoints = _edge_endpoints(edge)
        if endpoints is None:
            continue
        start, end = endpoints
        weight = edge_weight(edge)
        adjacency[start].append((end, weight))
        if edge.get("bidirectional", True):
            adjacency[end].append((start, weight))
    return {node: sorted(neighbors) for node, neighbors in adjacency.items()}


def shortest_path(adjacency: dict[str, list[str]], start: str, goal: str) -> list[str]:
    if start == goal:
        return [start]

    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        for neighbor in adjacency.get(node, []):
            if neighbor in seen:
                continue
            next_path = path + [neighbor]
            if neighbor == goal:
                return next_path
            seen.add(neighbor)
            queue.append((neighbor, next_path))
    return []


def shortest_weighted_path(
    weighted_adjacency: dict[str, list[tuple[str, int]]],
    start: str,
    goal: str,
) -> list[str]:
    if start == goal:
        return [start]

    costs: dict[str, int] = {start: 0}
    previous: dict[str, str] = {}
    heap: list[tuple[int, str]] = [(0, start)]

    while heap:
        cost, node = heapq.heappop(heap)
        if cost > costs.get(node, 1 << 62):
            continue
        if node == goal:
            break
        for neighbor, weight in weighted_adjacency.get(node, []):
            next_cost = cost + weight
            if next_cost < costs.get(neighbor, 1 << 62):
                costs[neighbor] = next_cost
                previous[neighbor] = node
                heapq.heappush(heap, (next_cost, neighbor))

    if goal not in costs:
        return []

    path = [goal]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path
