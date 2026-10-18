"""Route search and assembly (A2 Algorithms 3 and 4; FR6–FR8, FR16, [D3]–[D5], [D14], [D17]).

`find_route` runs a lexicographic Dijkstra on the routing graph and `assemble_route` turns
the winning path into legs and interchanges. The UI only ever sees the `Route` it returns.
"""

import heapq
import threading

from metro.errors import RouteCancelled
from metro.graph import RoutingGraph, interchange_stations
from metro.models import Interchange, Leg, Network, Route

Cost = tuple[int, int, int]  # (time_s, changes, stops)
PathArc = tuple[int, int, int, str]  # (from_node, to_node, time_s, kind)

CANCEL_CHECK_EVERY = 256  # pops between checks of the cancel event [D5]


def fastest_key(cost: Cost) -> Cost:
    """Heap key for `fastest`: time first, then changes, then stops."""
    return cost


def fewest_changes_key(cost: Cost) -> Cost:
    """Heap key for `fewest_changes` [Should]: changes first, then time, then stops."""
    time_s, changes, stops = cost
    return (changes, time_s, stops)


def fewest_stops_key(cost: Cost) -> Cost:
    """Heap key for `fewest_stops` [Should]: stops first, then time, then changes."""
    time_s, changes, stops = cost
    return (stops, time_s, changes)


KEY_FUNCTIONS = {
    "fastest": fastest_key,
    "fewest_changes": fewest_changes_key,
    "fewest_stops": fewest_stops_key,
}


def arc_cost(time_s: int, kind: str) -> Cost:
    """What one arc adds to a path's cost; a walk counts as a change [D17]."""
    if kind == "ride":
        return (time_s, 0, 1)
    return (time_s, 1, 0)  # transfer or walk


def find_route(graph: RoutingGraph, network: Network, src: str, dst: str,
               criterion: str = "fastest",
               cancel: threading.Event | None = None) -> Route | None:
    """Best route from station `src` to station `dst`, or None if there is none (ER7).

    Lexicographic Dijkstra with a super-source and early exit (A2 Alg. 3). Raises
    RouteCancelled if `cancel` is set while searching [D5].
    """
    key_of = KEY_FUNCTIONS[criterion]
    # dist and prev are dicts so a query only touches the nodes it explores [D3].
    cost: dict[int, Cost] = {}
    prev: dict[int, tuple[int, int, str]] = {}  # node -> (from_node, time_s, kind)
    heap: list[tuple[Cost, int]] = []
    # Super-source: every node of src starts at zero, so no change is charged at the origin.
    for node in graph.station_nodes.get(src, []):
        cost[node] = (0, 0, 0)
        heap.append(((0, 0, 0), node))
    heapq.heapify(heap)

    pops = 0
    while heap:
        key, node = heapq.heappop(heap)
        pops += 1
        if cancel is not None and pops % CANCEL_CHECK_EVERY == 0 and cancel.is_set():
            raise RouteCancelled()
        if key > key_of(cost[node]):
            continue  # lazy deletion: a better entry for this node was already popped
        if graph.nodes[node][0] == dst:
            # Early exit: stopping here means no false change is added at the destination.
            return assemble_route(graph, network, path_to(prev, node), src, dst)
        for to, time_s, kind in graph.adj[node]:
            step = arc_cost(time_s, kind)
            new = (cost[node][0] + step[0], cost[node][1] + step[1], cost[node][2] + step[2])
            if to not in cost or key_of(new) < key_of(cost[to]):
                cost[to] = new
                prev[to] = (node, time_s, kind)
                heapq.heappush(heap, (key_of(new), to))
    return None


def path_to(prev: dict[int, tuple[int, int, str]], end: int) -> list[PathArc]:
    """Follow `prev` back from `end` to a start node; return the arcs in travel order."""
    arcs: list[PathArc] = []
    node = end
    while node in prev:
        before, time_s, kind = prev[node]
        arcs.append((before, node, time_s, kind))
        node = before
    arcs.reverse()
    return arcs


def assemble_route(graph: RoutingGraph, network: Network, arcs: list[PathArc],
                   src: str, dst: str) -> Route:
    """Group path arcs into legs and interchanges (A2 Alg. 4, [D17]).

    Rides on one service form a RIDE leg. Whatever lies between two RIDE legs is one
    Interchange. Walks before the first or after the last ride are WALK legs.
    """
    pieces = split_into_pieces(graph, arcs)
    ride_positions = [i for i, p in enumerate(pieces) if p[0][3] == "ride"]
    legs: list[Leg] = []
    interchanges: list[Interchange] = []
    if not ride_positions:
        legs = [walk_leg(graph, p) for p in pieces]
    else:
        first, last = ride_positions[0], ride_positions[-1]
        legs += [walk_leg(graph, p) for p in pieces[:first]]
        for a, b in zip(ride_positions, ride_positions[1:]):
            legs.append(ride_leg(graph, network, pieces[a]))
            interchanges.append(
                make_interchange(graph, network, pieces[a], pieces[a + 1:b], pieces[b]))
        legs.append(ride_leg(graph, network, pieces[last]))
        legs += [walk_leg(graph, p) for p in pieces[last + 1:]]

    route = Route(src, dst, tuple(legs), tuple(interchanges),
                  total_s=sum(a[2] for a in arcs), stops=sum(a[3] == "ride" for a in arcs))
    check_invariants(route)
    return route


def split_into_pieces(graph: RoutingGraph, arcs: list[PathArc]) -> list[list[PathArc]]:
    """Cut the path into runs of rides on one service, and single transfer or walk arcs."""
    pieces: list[list[PathArc]] = []
    for arc in arcs:
        prev_piece = pieces[-1] if pieces else None
        same_ride = (prev_piece is not None and arc[3] == "ride" and prev_piece[-1][3] == "ride"
                     and graph.nodes[arc[0]][1] == graph.nodes[prev_piece[-1][0]][1])
        if same_ride:
            prev_piece.append(arc)
        else:
            pieces.append([arc])
    return pieces


def ride_leg(graph: RoutingGraph, network: Network, piece: list[PathArc]) -> Leg:
    """A RIDE leg from a run of ride arcs on one service."""
    service = network.services[graph.nodes[piece[0][0]][1]]
    stations = (graph.nodes[piece[0][0]][0],) + tuple(graph.nodes[a[1]][0] for a in piece)
    return Leg("RIDE", service.line_id, service.id, stations, sum(a[2] for a in piece),
               direction_label(network, service.id, stations[0], stations[1]))


def walk_leg(graph: RoutingGraph, piece: list[PathArc]) -> Leg:
    """A WALK leg from a single walk arc at the start or end of the path [D17]."""
    (start, end, time_s, _), = piece
    return Leg("WALK", None, None, (graph.nodes[start][0], graph.nodes[end][0]), time_s, None)


def make_interchange(graph: RoutingGraph, network: Network, before: list[PathArc],
                     between: list[list[PathArc]], after: list[PathArc]) -> Interchange:
    """One Interchange for everything between two RIDE legs: a transfer or a walk."""
    arcs = [arc for piece in between for arc in piece]
    off_station, off_service = graph.nodes[before[-1][1]]
    on_station, on_service = graph.nodes[after[0][0]]
    return Interchange(
        at_station=off_station,
        to_station=on_station,
        from_line=network.services[off_service].line_id,
        to_line=network.services[on_service].line_id,
        time_s=sum(a[2] for a in arcs),
        is_walk=any(a[3] == "walk" for a in arcs),
    )


def direction_label(network: Network, service_id: str, board: str, next_stop: str) -> str:
    """Direction text for a leg: "towards <terminus>" for a normal service, and for a loop
    "towards <next interchange>" in the travel direction, as a loop has no terminus [D14].
    """
    service = network.services[service_id]
    stops = service.stations
    i, j = stops.index(board), stops.index(next_stop)
    if not service.loop:
        end = stops[-1] if j > i else stops[0]
        return f"towards {network.stations[end].name}"
    step = 1 if j == (i + 1) % len(stops) else -1
    interchanges = interchange_stations(network)
    for k in range(1, len(stops) + 1):  # k == len(stops) comes back round to `board`
        station = stops[(i + step * k) % len(stops)]
        if station in interchanges:
            return f"towards {network.stations[station].name}"
    return f"towards {network.stations[next_stop].name}"


def check_invariants(route: Route) -> None:
    """The three Route invariants of PRD §5.3; a failure here is a bug in assembly."""
    rides = [leg for leg in route.legs if leg.kind == "RIDE"]
    assert all(len(leg.stations) >= 2 for leg in rides)
    assert len(route.interchanges) == max(len(rides) - 1, 0)
    assert (sum(leg.time_s for leg in route.legs)
            + sum(ic.time_s for ic in route.interchanges)) == route.total_s


def minutes(seconds: int) -> int:
    """Seconds rounded to the nearest minute for display: (s + 30) // 60 (PRD §5.3)."""
    return (seconds + 30) // 60
