"""Tests for alternative routes (FR17, [D47]): validity, order, determinism and speed."""

import os
import random
import statistics
import time

import pytest
from conftest import REAL_DATA, TOY_METRO

from metro.alternatives import (
    MAX_SLOWDOWN,
    find_alternative_routes,
    masked,
    route_badges,
    route_cost,
    signature,
)
from metro.data import load_network
from metro.graph import build_graph
from metro.router import KEY_FUNCTIONS, check_invariants, find_route

SLACK = 3 if os.environ.get("CI") else 1


@pytest.fixture(scope="module")
def toy():
    """toy_metro with its graph."""
    network = load_network(TOY_METRO)
    return network, build_graph(network)


@pytest.fixture(scope="module")
def real():
    """The real dataset with its graph."""
    network = load_network(REAL_DATA)
    return network, build_graph(network)


def ids_by_name(network, *names):
    """Station IDs for exact display names."""
    by_name = {st.name: sid for sid, st in network.stations.items()}
    return [by_name[name] for name in names]


@pytest.mark.parametrize("criterion", list(KEY_FUNCTIONS))
def test_first_alternative_is_the_best_route(toy, criterion):
    """The first route is exactly what find_route gives for the chosen criterion."""
    network, graph = toy
    routes = find_alternative_routes(graph, network, "A", "F", criterion)
    assert routes[0] == find_route(graph, network, "A", "F", criterion)


def test_tm2_and_tm6_are_both_offered(toy):
    """A -> F: the fastest is 720 s via Blue (TM2); fewest stops is 780 s via Green (TM6)."""
    network, graph = toy
    routes = find_alternative_routes(graph, network, "A", "F", "fastest")
    assert [(r.total_s, r.stops) for r in routes[:2]] == [(720, 3), (780, 2)]
    # TM2 and TM6 both have one interchange, so both win "Fewest interchanges".
    assert route_badges(routes[:2]) == [("Fastest", "Fewest interchanges"),
                                        ("Fewest interchanges", "Fewest stops")]


def test_routes_are_distinct_valid_and_between_the_right_stations(real):
    """Over 100 random pairs: no duplicates, each route is well-formed, none is absurdly slow."""
    network, graph = real
    rng = random.Random(47)
    ids = list(network.stations)
    for _ in range(100):
        src, dst = rng.sample(ids, 2)
        routes = find_alternative_routes(graph, network, src, dst)
        assert 1 <= len(routes) <= 3
        assert len({signature(r) for r in routes}) == len(routes)
        fastest = find_route(graph, network, src, dst).total_s
        for route in routes:
            check_invariants(route)
            assert (route.source, route.destination) == (src, dst)
            assert route.total_s >= fastest


def test_masked_alternatives_respect_the_slowdown_limit(real):
    """Beyond the three per-criterion routes, nothing is slower than 1.5 x the fastest."""
    network, graph = real
    rng = random.Random(48)
    ids = list(network.stations)
    for _ in range(100):
        src, dst = rng.sample(ids, 2)
        routes = find_alternative_routes(graph, network, src, dst, max_k=6)
        per_criterion = {signature(find_route(graph, network, src, dst, c)) for c in KEY_FUNCTIONS}
        fastest = min(r.total_s for r in routes)
        for route in routes:
            assert signature(route) in per_criterion or route.total_s <= MAX_SLOWDOWN * fastest


def test_max_k_limits_the_list(real):
    """max_k=1 gives only the best route; a larger max_k never gives more than asked."""
    network, graph = real
    src, dst = ids_by_name(network, "Samaypur Badli", "Noida City Centre")
    assert len(find_alternative_routes(graph, network, src, dst, max_k=1)) == 1
    assert len(find_alternative_routes(graph, network, src, dst, max_k=2)) == 2
    assert find_alternative_routes(graph, network, src, dst, max_k=0) == []


def test_result_is_deterministic(real):
    """The same call twice gives equal lists."""
    network, graph = real
    src, dst = ids_by_name(network, "Dwarka Sector 21", "Botanical Garden")
    assert find_alternative_routes(graph, network, src, dst) == \
        find_alternative_routes(graph, network, src, dst)


def test_no_route_gives_an_empty_list(toy):
    """With the walkway gone, H cannot reach A and there is nothing to offer (ER7)."""
    network, graph = toy
    from dataclasses import replace
    cut = replace(network, walkways=())
    assert find_alternative_routes(build_graph(cut), cut, "H", "A") == []


def test_masking_removes_only_the_listed_arcs(toy):
    """A masked copy lacks the banned arc, keeps the rest, and leaves the original alone."""
    network, graph = toy
    node = graph.station_nodes["A"][0]
    arc = graph.adj[node][0]
    copy = masked(graph, {(node, arc[0])})
    assert arc not in copy.adj[node] and arc in graph.adj[node]
    assert sum(map(len, copy.adj)) == sum(map(len, graph.adj)) - 1


def test_route_cost_counts_an_end_walk_as_a_change(toy):
    """TM10 A -> H is Red then a walk: the router charges the walk as a change."""
    network, graph = toy
    route = find_route(graph, network, "A", "H")
    assert route_cost(route) == (route.total_s, 1, route.stops)


def test_alternatives_p95_under_50_ms(real):
    """Alternatives for 300 seeded random pairs: p95 <= 50 ms, so they can run on the UI
    thread without a visible pause ([D47])."""
    network, graph = real
    rng = random.Random(29)
    ids = list(network.stations)
    samples = []
    for _ in range(300):
        src, dst = rng.sample(ids, 2)
        start = time.perf_counter()
        find_alternative_routes(graph, network, src, dst)
        samples.append(time.perf_counter() - start)
    assert statistics.quantiles(samples, n=20)[-1] <= 0.050 * SLACK
