"""Floyd–Warshall oracle for the toy fixtures (A2 Algorithm 8, [D28]).

Independent of the router: it uses time only, has no early exit and no super-source,
and takes the minimum over all nodes of the source and destination stations.
"""

import math

from metro.graph import RoutingGraph


def all_pairs_times(graph: RoutingGraph) -> dict[tuple[str, str], float]:
    """Shortest time between every ordered pair of stations; math.inf if unreachable."""
    n = len(graph.nodes)
    dist = [[math.inf] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
        for to, time_s, _ in graph.adj[i]:
            dist[i][to] = min(dist[i][to], time_s)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
    return {(s, t): min(dist[i][j] for i in graph.station_nodes[s] for j in graph.station_nodes[t])
            for s in graph.station_nodes for t in graph.station_nodes}
