from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class Edge:
    origin: str
    target: str
    cost: float


class Graph:
    """Simple undirected weighted graph with Dijkstra support."""

    def __init__(self, nodes: Iterable[str], edges: Iterable[Tuple[str, str, float]]) -> None:
        self.nodes: List[str] = list(nodes)
        self._adjacency: Dict[str, List[Tuple[str, float]]] = {node: [] for node in self.nodes}

        for origin, target, cost in edges:
            self._add_edge(origin, target, float(cost))

    def _add_edge(self, origin: str, target: str, cost: float) -> None:
        self._adjacency[origin].append((target, cost))
        self._adjacency[target].append((origin, cost))

    def neighbors(self, node: str) -> List[Tuple[str, float]]:
        return self._adjacency[node]

    def dijkstra(self, source: str) -> Tuple[Dict[str, float], Dict[str, str]]:
        """Compute single-source shortest paths using Dijkstra.

        distances[v] stores the best-known distance from source to v, and
        predecessors[v] remembers the previous node along the shortest path.
        """
        distances: Dict[str, float] = {node: float("inf") for node in self.nodes}
        predecessors: Dict[str, str] = {}
        distances[source] = 0.0

        queue: List[Tuple[float, str]] = [(0.0, source)]

        while queue:
            distance_u, u = heappop(queue)
            if distance_u > distances[u]:
                continue

            for v, cost in self.neighbors(u):
                candidate = distance_u + cost
                if candidate < distances[v]:
                    distances[v] = candidate
                    predecessors[v] = u
                    heappush(queue, (candidate, v))

        return distances, predecessors

    def shortest_path(self, source: str, target: str) -> Tuple[float, List[str]]:
        """Recover both length and explicit path between source and target."""
        distances, predecessors = self.dijkstra(source)
        cost = distances[target]
        if cost == float("inf"):
            raise ValueError(f"No path between {source} and {target}.")

        path: List[str] = [target]
        while path[-1] != source:
            path.append(predecessors[path[-1]])
        path.reverse()
        return cost, path

    def path_cost(self, path: List[str]) -> float:
        """Return the total cost of walking along the given node sequence."""
        if len(path) < 2:
            return 0.0

        total_cost = 0.0
        for u, v in zip(path[:-1], path[1:]):
            edge_cost = next((cost for neighbor, cost in self.neighbors(u) if neighbor == v), None)
            if edge_cost is None:
                raise ValueError(f"Edge {u}-{v} not present in graph.")
            total_cost += edge_cost
        return total_cost
