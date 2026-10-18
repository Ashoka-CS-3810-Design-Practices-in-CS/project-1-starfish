"""The line-expanded routing graph (A2 Algorithm 2; FR2, [D1], [D2]).

A plain station graph cannot charge interchanges correctly: the cost of leaving a station
depends on which line you arrived on. So each station is split into one node per service
that stops there, and changing train becomes a real `transfer` arc with a real cost.
"""

from dataclasses import dataclass

from metro.models import Network
from metro.validate import consecutive_pairs

Arc = tuple[int, int, str]  # (to_node, time_s, kind) where kind is ride, transfer or walk


@dataclass(frozen=True)
class RoutingGraph:
    """Adjacency-list graph whose nodes are (station_id, service_id) pairs."""

    nodes: list[tuple[str, str]]  # index -> (station_id, service_id)
    node_of: dict[tuple[str, str], int]
    adj: list[list[Arc]]
    station_nodes: dict[str, list[int]]  # station -> its nodes


def build_graph(network: Network) -> RoutingGraph:
    """Build the routing graph; closed stations get no node, cutting their services [D1].

    Nodes are numbered in sorted (station, service) order, so the same data always gives
    the same numbering, and therefore the same tie-breaks in Dijkstra ([D4]).
    """
    open_ids = {sid for sid, st in network.stations.items() if not st.closed}
    nodes = sorted({(station, service.id)
                    for service in network.services.values()
                    for station in service.stations if station in open_ids})
    node_of = {node: i for i, node in enumerate(nodes)}
    station_nodes: dict[str, list[int]] = {}
    for i, (station, _) in enumerate(nodes):
        station_nodes.setdefault(station, []).append(i)

    adj: list[list[Arc]] = [[] for _ in nodes]
    add_ride_arcs(network, node_of, adj)
    add_transfer_arcs(network, nodes, station_nodes, adj)
    add_walk_arcs(network, station_nodes, adj)
    for arcs in adj:
        arcs.sort()
    return RoutingGraph(nodes, node_of, adj, station_nodes)


def add_ride_arcs(network: Network, node_of: dict[tuple[str, str], int],
                  adj: list[list[Arc]]) -> None:
    """One ride arc each way per hop of each service, including a loop's closing hop."""
    time_of = {(seg.line_id, frozenset((seg.a, seg.b))): seg.time_s for seg in network.segments}
    for service in network.services.values():
        for a, b in consecutive_pairs(service.stations, service.loop):
            na, nb = node_of.get((a, service.id)), node_of.get((b, service.id))
            if na is None or nb is None:
                continue  # one end is closed
            time_s = time_of[(service.line_id, frozenset((a, b)))]
            adj[na].append((nb, time_s, "ride"))
            adj[nb].append((na, time_s, "ride"))


def add_transfer_arcs(network: Network, nodes: list[tuple[str, str]],
                      station_nodes: dict[str, list[int]], adj: list[list[Arc]]) -> None:
    """A transfer arc between every ordered pair of services at a station.

    A station with k services gets k(k-1) arcs, minus pairs listed in `no_transfer`.
    """
    for station, ids in station_nodes.items():
        for n1 in ids:
            for n2 in ids:
                s1, s2 = nodes[n1][1], nodes[n2][1]
                if n1 == n2 or frozenset((s1, s2)) in network.no_transfer:
                    continue
                adj[n1].append((n2, transfer_time(network, station, s1, s2), "transfer"))


def transfer_time(network: Network, station: str, service_a: str, service_b: str) -> int:
    """Seconds to change between two services at a station (PRD §4.2 rules).

    An override for this station and pair wins; otherwise a branch change on the same line
    costs `default_same_line_s` and a change to another line costs `default_other_line_s`.
    """
    for ov in network.overrides:
        if ov.station == station and {ov.service_a, ov.service_b} == {service_a, service_b}:
            return ov.time_s
    same_line = network.services[service_a].line_id == network.services[service_b].line_id
    return network.default_same_line_s if same_line else network.default_other_line_s


def add_walk_arcs(network: Network, station_nodes: dict[str, list[int]],
                  adj: list[list[Arc]]) -> None:
    """Walk arcs from every node of station a to every node of station b, and back unless
    the walkway is one-way [D2]."""
    for walk in network.walkways:
        nodes_a = station_nodes.get(walk.a, [])
        nodes_b = station_nodes.get(walk.b, [])
        for na in nodes_a:
            for nb in nodes_b:
                adj[na].append((nb, walk.time_s, "walk"))
                if not walk.one_way:
                    adj[nb].append((na, walk.time_s, "walk"))
