"""Performance tests T29 and T30 (PRD §7, [D18], [D30]).

Plain time.perf_counter timings with p95 from statistics.quantiles. On CI the budgets are
multiplied by 3, because shared CI machines are slower and noisier.
"""

import os
import random
import statistics
import time

from conftest import REAL_DATA

from metro.data import load_network
from metro.graph import build_graph
from metro.models import Line, Network, Segment, Service, Station
from metro.router import find_route
from metro.search import build_index, search

SLACK = 3 if os.environ.get("CI") else 1


def p95(samples: list[float]) -> float:
    """95th percentile of a list of timings."""
    return statistics.quantiles(samples, n=20)[-1]


def timed(fn, *args) -> float:
    """Seconds taken by one call of fn(*args)."""
    start = time.perf_counter()
    fn(*args)
    return time.perf_counter() - start


def test_t29_load_and_validate_under_one_second():
    """T29: data load + validation <= 1 s."""
    assert timed(load_network, REAL_DATA) <= 1.0 * SLACK


def test_t29_route_query_p95():
    """T29: route query p95 over 1 000 seeded random pairs <= 50 ms."""
    network = load_network(REAL_DATA)
    graph = build_graph(network)
    rng = random.Random(29)
    ids = list(network.stations)
    samples = [timed(find_route, graph, network, *rng.sample(ids, 2)) for _ in range(1000)]
    assert p95(samples) <= 0.050 * SLACK


def test_t29_search_keystroke_p95():
    """T29: search p95 over every prefix of every name plus 200 typos <= 50 ms."""
    network = load_network(REAL_DATA)
    index = build_index(network.stations.values())
    names = [st.name for st in network.stations.values()]
    queries = [name[:k] for name in names for k in range(1, len(name) + 1)]
    rng = random.Random(29)
    for _ in range(200):
        name = list(rng.choice(names))
        name[rng.randrange(len(name))] = rng.choice("abcdefghijklmnopqrstuvwxyz")
        queries.append("".join(name))
    samples = [timed(search, index, q) for q in queries]
    assert p95(samples) <= 0.050 * SLACK


def synthetic_network(seed: int = 30) -> Network:
    """A 10x network for T30: 9 lines of 330 stations on a grid, about 12% shared.

    Every 8th station of lines 1-8 is replaced by the station at the same position on a
    random earlier line, which creates the interchanges.
    """
    rng = random.Random(seed)
    station_lists: list[list[str]] = []
    for i in range(9):
        ids = [f"L{i}-{j}" for j in range(330)]
        if i > 0:
            for j in range(0, 330, 8):
                ids[j] = station_lists[rng.randrange(i)][j]
        station_lists.append(ids)
    all_ids = sorted({sid for ids in station_lists for sid in ids})
    stations = {sid: Station(sid, sid, 28.0 + int(sid.split("-")[1]) / 1000,
                             77.0 + int(sid[1]) / 100) for sid in all_ids}
    lines, segments = {}, []
    for i, ids in enumerate(station_lists):
        service = Service(f"S{i}", f"L{i}", tuple(ids))
        lines[f"L{i}"] = Line(f"L{i}", f"Line {i}", "#000000", (service,))
        segments += [Segment(f"G{i}-{j}", f"L{i}", a, b, rng.randint(60, 240))
                     for j, (a, b) in enumerate(zip(ids, ids[1:]))]
    services = {s.id: s for line in lines.values() for s in line.services}
    return Network(stations, lines, services, tuple(segments), (), 240, 120, (), frozenset())


def test_t30_synthetic_ten_times_network():
    """T30: route p95 on the synthetic ~3 000-station network <= 100 ms."""
    network = synthetic_network()
    assert len(network.stations) > 2500
    graph = build_graph(network)
    rng = random.Random(30)
    ids = list(network.stations)
    samples = [timed(find_route, graph, network, *rng.sample(ids, 2)) for _ in range(300)]
    assert p95(samples) <= 0.100 * SLACK
