"""Router tests on the toy fixtures (A2 Algs. 3–4; TM1–TM11, TL1–TL5, oracle agreement)."""

import threading
from pathlib import Path

import pytest
from conftest import TOY_BRANCH_LOOP, TOY_METRO, add_override, close_stations
from oracle import all_pairs_times

from metro.data import load_network
from metro.errors import RouteCancelled
from metro.graph import build_graph
from metro.router import find_route, minutes


def route(folder_or_net, src, dst, criterion="fastest"):
    """Load (if needed), build the graph and run one query."""
    net = load_network(folder_or_net) if isinstance(folder_or_net, Path) else folder_or_net
    return find_route(build_graph(net), net, src, dst, criterion)


def shape(r):
    """A compact description of a route: [(kind, service, stations), ...]."""
    return [(leg.kind, leg.service_id, "".join(leg.stations)) for leg in r.legs]


# ---- toy_metro (PRD §9.2) -------------------------------------------------------------


def test_tm1_single_red_leg():
    """TM1: A->D is one Red leg, 420 s, 3 stops, 0 interchanges, towards D."""
    r = route(TOY_METRO, "A", "D")
    assert shape(r) == [("RIDE", "R1", "ABCD")]
    assert (r.total_s, minutes(r.total_s), r.stops, r.interchanges) == (420, 7, 3, ())
    assert r.legs[0].direction == "towards Station D"


def test_tm2_change_at_c():
    """TM2: A->F rides Red to C, changes to Blue (240 s), rides to F: 720 s."""
    r = route(TOY_METRO, "A", "F")
    assert shape(r) == [("RIDE", "R1", "ABC"), ("RIDE", "B1", "CF")]
    assert [leg.time_s for leg in r.legs] == [300, 180]
    (ic,) = r.interchanges
    assert (ic.at_station, ic.from_line, ic.to_line, ic.time_s, ic.is_walk) == \
        ("C", "RED", "BLUE", 240, False)
    assert (r.total_s, minutes(r.total_s), r.stops) == (720, 12, 3)


def test_tm3_no_false_change_at_destination():
    """TM3: A->C stays on Red; arriving at C never adds a change to Blue."""
    r = route(TOY_METRO, "A", "C")
    assert shape(r) == [("RIDE", "R1", "ABC")]
    assert (r.total_s, r.interchanges) == (300, ())


def test_tm4_through_c_is_not_a_change():
    """TM4: E->F is one Blue leg through C, 360 s."""
    r = route(TOY_METRO, "E", "F")
    assert shape(r) == [("RIDE", "B1", "ECF")]
    assert (r.total_s, r.interchanges) == (360, ())
    assert r.legs[0].direction == "towards Station F"


def test_tm5_reverse_direction():
    """TM5: D->E is Red D->C, change at C, Blue C->E, 540 s."""
    r = route(TOY_METRO, "D", "E")
    assert shape(r) == [("RIDE", "R1", "DC"), ("RIDE", "B1", "CE")]
    assert (r.total_s, len(r.interchanges)) == (540, 1)
    assert r.legs[0].direction == "towards Station A"
    assert r.legs[1].direction == "towards Station E"


def test_tm6_fewest_stops_goes_via_green():
    """TM6: A->F by fewest stops goes via B and Green: 780 s, 2 stops, change at B."""
    r = route(TOY_METRO, "A", "F", "fewest_stops")
    assert shape(r) == [("RIDE", "R1", "AB"), ("RIDE", "G1", "BF")]
    assert (r.total_s, r.stops) == (780, 2)
    assert r.interchanges[0].at_station == "B"


def test_tm7_override_makes_b_faster():
    """TM7: with B Red<->Green at 120 s, A->F goes via B in 660 s."""
    net = add_override(load_network(TOY_METRO), "B", "R1", "G1", 120)
    r = route(net, "A", "F")
    assert shape(r) == [("RIDE", "R1", "AB"), ("RIDE", "G1", "BF")]
    assert r.total_s == 660 and r.interchanges[0].time_s == 120


def test_tm8_closed_c():
    """TM8: with C closed, A->F is 780 s via B; A->D and E->F have no route (None)."""
    net = close_stations(load_network(TOY_METRO), "C")
    assert route(net, "A", "F").total_s == 780
    assert route(net, "A", "D") is None
    assert route(net, "E", "F") is None


def test_tm9_walk_leg_at_start():
    """TM9: D->I is a WALK leg D->H then Yellow H->I: 480 s, 0 interchanges [D17]."""
    r = route(TOY_METRO, "D", "I")
    assert shape(r) == [("WALK", None, "DH"), ("RIDE", "Y1", "HI")]
    assert [leg.time_s for leg in r.legs] == [300, 180]
    assert (r.total_s, r.interchanges) == (480, ())


def test_tm10_walk_leg_at_end():
    """TM10: A->H is Red A->D then a WALK leg D->H: 720 s, 0 interchanges."""
    r = route(TOY_METRO, "A", "H")
    assert shape(r) == [("RIDE", "R1", "ABCD"), ("WALK", None, "DH")]
    assert (r.total_s, r.interchanges) == (720, ())


def test_tm11_walk_interchange_in_the_middle():
    """TM11: A->I walks from D to H between two rides: one walk interchange, 900 s."""
    r = route(TOY_METRO, "A", "I")
    assert shape(r) == [("RIDE", "R1", "ABCD"), ("RIDE", "Y1", "HI")]
    (ic,) = r.interchanges
    assert (ic.at_station, ic.to_station, ic.time_s, ic.is_walk) == ("D", "H", 300, True)
    assert r.total_s == 900


# ---- toy_branch_loop (PRD §9.3) --------------------------------------------------------


def test_tl1_branch_change_at_j():
    """TL1: A->D is 540 s, 3 stops, one Orange->Orange change at J."""
    r = route(TOY_BRANCH_LOOP, "A", "D")
    assert shape(r) == [("RIDE", "O1", "ABJ"), ("RIDE", "O2", "JD")]
    (ic,) = r.interchanges
    assert (ic.at_station, ic.from_line, ic.to_line, ic.time_s) == ("J", "ORANGE", "ORANGE", 120)
    assert (r.total_s, r.stops) == (540, 3)


def test_tl2_passing_j_is_not_a_change():
    """TL2: A->C is 360 s, 3 stops, 0 interchanges."""
    r = route(TOY_BRANCH_LOOP, "A", "C")
    assert shape(r) == [("RIDE", "O1", "ABJC")]
    assert (r.total_s, r.stops, r.interchanges) == (360, 3, ())


def test_tl3_branch_to_main():
    """TL3: D->C is 420 s with one change at J."""
    r = route(TOY_BRANCH_LOOP, "D", "C")
    assert r.total_s == 420
    assert [ic.at_station for ic in r.interchanges] == ["J"]


def test_tl4_loop_closing_segment():
    """TL4: C->L4 uses the loop's closing segment: 120 s, 1 stop."""
    r = route(TOY_BRANCH_LOOP, "C", "L4")
    assert shape(r) == [("RIDE", "V", "CL4")]
    assert (r.total_s, r.stops) == (120, 1)


def test_tl5_loop_direction_is_deterministic():
    """TL5: A->L3 is 840 s, 5 stops, change at C, same loop direction every run."""
    net = load_network(TOY_BRANCH_LOOP)
    graph = build_graph(net)
    results = {find_route(graph, net, "A", "L3") for _ in range(20)}
    assert len(results) == 1
    (r,) = results
    assert (r.total_s, r.stops) == (840, 5)
    assert [ic.at_station for ic in r.interchanges] == ["C"]
    assert r.total_s == all_pairs_times(graph)[("A", "L3")]


def test_loop_direction_label_is_never_a_terminus():
    """[D14] On a loop the label names the next interchange in the travel direction."""
    r = route(TOY_BRANCH_LOOP, "L2", "L3")
    assert r.legs[0].direction == "towards Station C"  # only interchange on the loop


# ---- oracle agreement ([D28]) and other properties --------------------------------------


@pytest.mark.parametrize("folder", [TOY_METRO, TOY_BRANCH_LOOP])
def test_dijkstra_agrees_with_floyd_warshall_on_every_pair(folder):
    """Fastest-route time equals the Floyd–Warshall time for every ordered pair."""
    net = load_network(folder)
    graph = build_graph(net)
    for (s, t), expected in all_pairs_times(graph).items():
        if s == t:
            continue
        r = find_route(graph, net, s, t)
        assert (r.total_s if r else float("inf")) == expected, (s, t)


def test_unknown_station_gives_none():
    """A station with no nodes (unknown or closed) gives None, not an exception."""
    assert route(TOY_METRO, "A", "NOPE") is None


def test_cancel_event_raises(monkeypatch):
    """[D5] A set cancel event stops the search with RouteCancelled."""
    net = load_network(TOY_METRO)
    graph = build_graph(net)
    cancel = threading.Event()
    cancel.set()
    # The toy graph is too small to reach 256 pops, so check on every pop.
    monkeypatch.setattr("metro.router.CANCEL_CHECK_EVERY", 1)
    with pytest.raises(RouteCancelled):
        find_route(graph, net, "A", "I", cancel=cancel)


def test_minutes_rounding():
    """Display minutes round half up: 29 s -> 0, 30 s -> 1, 89 s -> 1, 90 s -> 2."""
    assert [minutes(s) for s in (29, 30, 89, 90)] == [0, 1, 1, 2]
