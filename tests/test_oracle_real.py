"""T19: Dijkstra agrees with networkx on every ordered pair of real stations ([D28]).

networkx runs on a copy of the routing graph with a super-source (to every node of the
source station) and a super-sink per station (from every node of that station).
"""

import networkx as nx
import pytest
from conftest import REAL_DATA

from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route


def networkx_times(graph, src: str) -> dict[str, float]:
    """networkx shortest time from station `src` to every station it can reach."""
    g = nx.DiGraph()
    for i, arcs in enumerate(graph.adj):
        for to, time_s, _ in arcs:
            g.add_edge(i, to, weight=time_s)
    for station, nodes in graph.station_nodes.items():
        for node in nodes:
            g.add_edge(node, ("sink", station), weight=0)
    for node in graph.station_nodes[src]:
        g.add_edge("source", node, weight=0)
    lengths = nx.single_source_dijkstra_path_length(g, "source")
    return {key[1]: t for key, t in lengths.items() if isinstance(key, tuple)}


@pytest.mark.slow
def test_t19_all_pairs_match_networkx():
    """Every ordered pair of open stations: same time, and every hop is a real arc."""
    network = load_network(REAL_DATA)
    graph = build_graph(network)
    linked = {(graph.nodes[i][0], graph.nodes[to][0])
              for i, arcs in enumerate(graph.adj) for to, _, _ in arcs}
    for src in graph.station_nodes:
        expected = networkx_times(graph, src)
        for dst in graph.station_nodes:
            if src == dst:
                continue
            route = find_route(graph, network, src, dst)
            assert (route.total_s if route else None) == expected.get(dst), (src, dst)
            stations = [s for leg in route.legs for s in leg.stations] if route else []
            hops = [(a, b) for a, b in zip(stations, stations[1:]) if a != b]
            assert all(hop in linked for hop in hops), (src, dst)
