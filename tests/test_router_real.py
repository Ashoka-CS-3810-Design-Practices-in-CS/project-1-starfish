"""Router tests on the real Delhi Metro data (T1–T10, T20; golden routes [D22]).

Golden routes check structure only (lines and interchange stations); minutes are checked
against the oracle, not hard-coded, because running times are estimates.
"""

import json
import random
from pathlib import Path

import pytest
from conftest import REAL_DATA, TOY_METRO, add_override, close_stations, shuffled_copy

from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route

GOLDEN = json.loads((Path(__file__).parent / "golden" / "routes.json").read_text())


@pytest.fixture(scope="module")
def real():
    """The real network and its graph, loaded once for this file."""
    network = load_network(REAL_DATA)
    return network, build_graph(network)


def lines_and_changes(route):
    """(line IDs of the RIDE legs, interchange stations) of a route."""
    return ([leg.line_id for leg in route.legs if leg.kind == "RIDE"],
            [ic.at_station for ic in route.interchanges])


@pytest.mark.parametrize("entry", GOLDEN, ids=lambda e: f"{e['from']}-{e['to']}")
def test_golden_route_structure(real, entry):
    """[D22] Each golden route has the expected line sequence and interchange stations."""
    network, graph = real
    route = find_route(graph, network, entry["from"], entry["to"])
    assert lines_and_changes(route) == (entry["lines"], entry["interchanges"])


def test_t1_kashmere_gate_to_rajiv_chowk(real):
    """T1: one Yellow leg and no interchange."""
    network, graph = real
    assert lines_and_changes(find_route(graph, network, "KSHG", "RJCK")) == (["YELLOW"], [])


def test_t2_janakpuri_west_transfer_override(real):
    """T2: with the Janakpuri West Blue<->Magenta transfer made huge, the route from
    Uttam Nagar East to Botanical Garden must be Blue-only with 0 interchanges."""
    network, _ = real
    network = add_override(network, "JNPW", "BLUE-MAIN", "MAG-1", 10_000)
    route = find_route(build_graph(network), network, "UMNA", "BTGD")
    assert [leg.service_id for leg in route.legs] == ["BLUE-MAIN"]
    assert route.interchanges == ()


def test_t3_single_change_at_rajiv_chowk(real):
    """T3: Samaypur Badli -> Noida City Centre changes Yellow -> Blue at Rajiv Chowk."""
    network, graph = real
    route = find_route(graph, network, "SRBL", "NDCY")
    assert lines_and_changes(route) == (["YELLOW", "BLUE"], ["RJCK"])


def test_t4_blue_branch_change_at_yamuna_bank(real):
    """T4: exactly one Blue -> Blue interchange, at Yamuna Bank."""
    network, graph = real
    route = find_route(graph, network, "NECT", "VASH")
    (ic,) = route.interchanges
    assert (ic.at_station, ic.from_line, ic.to_line) == ("YMBK", "BLUE", "BLUE")
    assert [leg.service_id for leg in route.legs] == ["BLUE-MAIN", "BLUE-BR"]


def test_t5_walkway_is_a_walk_leg(real):
    """T5: Dhaula Kuan -> Lajpat Nagar starts with a WALK leg that is not an interchange."""
    network, graph = real
    route = find_route(graph, network, "DHKN", "LTNR")
    assert route.legs[0].kind == "WALK"
    assert route.legs[0].stations == ("DHKN", "DDSC")
    assert route.interchanges == ()


def test_t6_green_branch_change_at_ashok_park_main(real):
    """T6: Kirti Nagar -> Mundka changes Green branch -> Green main at Ashok Park Main."""
    network, graph = real
    route = find_route(graph, network, "KTNR", "MNDK")
    assert [leg.service_id for leg in route.legs] == ["GREEN-BR", "GREEN-MAIN"]
    assert [ic.at_station for ic in route.interchanges] == ["AKPK"]


def test_t7_magenta_sections_never_joined(real):
    """T7: no route changes directly between the two Magenta sections."""
    network, graph = real
    for src in network.services["MAG-2"].stations:
        for dst in network.services["MAG-1"].stations:
            route = find_route(graph, network, src, dst)
            services = [leg.service_id for leg in route.legs if leg.kind == "RIDE"]
            assert ("MAG-2", "MAG-1") not in set(zip(services, services[1:]))


def test_t8_pink_loop_direction_label(real):
    """T8: on the Pink ring the label is an interchange name, and reversing the pair
    reverses the direction."""
    network, graph = real
    forward = find_route(graph, network, "SNNR", "ASHR").legs[0].direction
    backward = find_route(graph, network, "ASHR", "SNNR").legs[0].direction
    assert forward == "towards Dilli Haat - INA"
    assert backward == "towards Lajpat Nagar"


def test_t9_closed_station_on_the_only_path():
    """T9: closing the only link station gives None; on real data a closure reroutes."""
    toy = close_stations(load_network(TOY_METRO), "C")
    assert find_route(build_graph(toy), toy, "A", "D") is None
    net = close_stations(load_network(REAL_DATA), "YMBK")
    route = find_route(build_graph(net), net, "NECT", "VASH")
    assert route is not None and "YMBK" not in [s for leg in route.legs for s in leg.stations]


def test_t10_deterministic(real, tmp_path):
    """T10: the same query 100 times, and with every JSON file shuffled, gives equal Routes."""
    network, graph = real
    first = find_route(graph, network, "DLCK", "KJMR")
    assert all(find_route(graph, network, "DLCK", "KJMR") == first for _ in range(100))
    for seed in range(3):
        shuffled = load_network(shuffled_copy(REAL_DATA, tmp_path / str(seed), seed))
        assert find_route(build_graph(shuffled), shuffled, "DLCK", "KJMR") == first


def test_t20_closing_a_station_never_shortens_a_route(real):
    """T20 (metamorphic, [D29]): 200 seeded random closures never make any route faster."""
    network, graph = real
    rng = random.Random(20)
    ids = list(network.stations)
    for _ in range(200):
        src, dst, closed = rng.sample(ids, 3)
        before = find_route(graph, network, src, dst)
        variant = close_stations(network, closed)
        after = find_route(build_graph(variant), variant, src, dst)
        if after is not None:
            assert before is not None and after.total_s >= before.total_s


def key_changes(route) -> int:
    """Changes as counted by the search key: interchanges plus WALK legs [D17]."""
    return len(route.interchanges) + sum(leg.kind == "WALK" for leg in route.legs)


def test_t21_fewest_changes_and_fewest_stops(real):
    """T21 [Should]: fewest_changes never has more changes than fastest, and the reported
    interchange count never exceeds the key's count; fewest_stops never has more stops."""
    network, graph = real
    rng = random.Random(21)
    ids = list(network.stations)
    for _ in range(300):
        src, dst = rng.sample(ids, 2)
        fastest = find_route(graph, network, src, dst)
        fewest = find_route(graph, network, src, dst, "fewest_changes")
        stops = find_route(graph, network, src, dst, "fewest_stops")
        assert key_changes(fewest) <= key_changes(fastest)
        assert len(fewest.interchanges) <= key_changes(fewest)
        assert fewest.total_s >= fastest.total_s
        assert stops.stops <= fastest.stops
