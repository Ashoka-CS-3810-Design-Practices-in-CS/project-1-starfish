"""Alternative routes between two stations (FR17, [D47]).

The best route is found as usual. Alternatives come from two places: the best route under
each of the other criteria, and the best route after "masking" part of a route we already
have, so the search has to find another way. Masking works on a copy of the graph, so
`router.py` is untouched; this file only calls `find_route`.
"""

from dataclasses import replace

from metro.describe import CRITERION_LABELS
from metro.graph import RoutingGraph
from metro.models import Leg, Network, Route
from metro.router import KEY_FUNCTIONS, Cost, find_route

MAX_SLOWDOWN = 1.5  # a masked alternative may take at most 50% longer than the fastest route
MAX_ROUNDS = 2  # masking the best route, then masking what that produced


def route_cost(route: Route) -> Cost:
    """(time_s, changes, stops) as the router counts them: an end walk is also a change."""
    walks = sum(leg.kind == "WALK" for leg in route.legs)
    return (route.total_s, len(route.interchanges) + walks, route.stops)


def signature(route: Route) -> tuple:
    """Two routes are the same journey if every leg uses the same service and stations."""
    return tuple((leg.kind, leg.service_id, leg.stations) for leg in route.legs)


def masked(graph: RoutingGraph, banned: set[tuple[int, int]]) -> RoutingGraph:
    """A copy of the graph without the arcs listed as (from_node, to_node)."""
    adj = [[arc for arc in arcs if (node, arc[0]) not in banned]
           for node, arcs in enumerate(graph.adj)]
    return replace(graph, adj=adj)


def change_arcs_at(graph: RoutingGraph, stations: set[str]) -> set[tuple[int, int]]:
    """Every transfer and walk arc that starts at one of the stations: no changing there."""
    return {(node, arc[0]) for station in stations for node in graph.station_nodes[station]
            for arc in graph.adj[node] if arc[2] != "ride"}


def middle_hop(graph: RoutingGraph, leg: Leg) -> set[tuple[int, int]]:
    """The middle hop of a ride leg, both directions: a route cannot use that stretch."""
    i = (len(leg.stations) - 1) // 2
    a = graph.node_of[(leg.stations[i], leg.service_id)]
    b = graph.node_of[(leg.stations[i + 1], leg.service_id)]
    return {(a, b), (b, a)}


def masks_for(graph: RoutingGraph, route: Route) -> list[set[tuple[int, int]]]:
    """One mask per way to avoid part of the route: each change station, each ride's middle."""
    masks = [change_arcs_at(graph, {ic.at_station, ic.to_station}) for ic in route.interchanges]
    masks += [middle_hop(graph, leg) for leg in route.legs if leg.kind == "RIDE"]
    return masks


def rerouted(graph: RoutingGraph, network: Network, base: Route, criterion: str) -> list[Route]:
    """The best route for each mask of `base`; masks that cut every way give nothing."""
    found = []
    for mask in masks_for(graph, base):
        route = find_route(masked(graph, mask), network, base.source, base.destination, criterion)
        if route is not None:
            found.append(route)
    return found


def find_alternative_routes(graph: RoutingGraph, network: Network, src: str, dst: str,
                            criterion: str = "fastest", max_k: int = 3) -> list[Route]:
    """Up to `max_k` different routes, the best for `criterion` first.

    Next come the best routes of the other criteria, then masked alternatives ranked by
    `criterion` and dropped if more than MAX_SLOWDOWN times slower than the fastest route.
    The result is the same on every run.
    """
    best = find_route(graph, network, src, dst, criterion)
    if best is None or max_k < 1:
        return []
    routes = [best]
    for other in KEY_FUNCTIONS:
        if other == criterion:
            continue
        route = find_route(graph, network, src, dst, other)
        if route is not None and signature(route) not in {signature(r) for r in routes}:
            routes.append(route)
    limit = MAX_SLOWDOWN * min(r.total_s for r in routes)
    key = KEY_FUNCTIONS[criterion]
    pool = routes[:]
    for _ in range(MAX_ROUNDS):
        fresh = []
        for base in pool:
            for route in rerouted(graph, network, base, criterion):
                known = {signature(r) for r in routes + fresh}
                if signature(route) not in known and route.total_s <= limit:
                    fresh.append(route)
        fresh.sort(key=lambda r: (key(route_cost(r)), signature(r)))
        routes += fresh
        pool = fresh
        if len(routes) >= max_k or not fresh:
            break
    return routes[:max_k]


def route_badges(routes: list[Route]) -> list[tuple[str, ...]]:
    """For each route, the criteria it wins among `routes` (ties win together)."""
    costs = [route_cost(r) for r in routes]
    best = {name: min(c[i] for c in costs)
            for name, i in zip(CRITERION_LABELS.values(), (0, 1, 2))}
    return [tuple(name for name, i in zip(CRITERION_LABELS.values(), (0, 1, 2))
                  if cost[i] == best[name]) for cost in costs]
