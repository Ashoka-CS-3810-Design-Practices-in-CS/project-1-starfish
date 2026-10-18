"""Tests for the line-expanded routing graph (A2 Alg. 2; FR2; TM0, TL0)."""

from collections import Counter
from dataclasses import replace

from conftest import TOY_BRANCH_LOOP, TOY_METRO, add_override, close_stations, shuffled_copy

from metro.data import load_network
from metro.graph import build_graph, transfer_time


def arc_kinds(graph) -> Counter:
    """Count the arcs of each kind."""
    return Counter(kind for arcs in graph.adj for _, _, kind in arcs)


def arcs_at(graph, kind: str) -> set[str]:
    """Stations where arcs of `kind` start."""
    return {graph.nodes[i][0] for i, arcs in enumerate(graph.adj) for _, _, k in arcs if k == kind}


def test_tm0_toy_metro_counts():
    """TM0: 11 nodes and 22 arcs (14 ride, 6 transfer, 2 walk)."""
    graph = build_graph(load_network(TOY_METRO))
    assert len(graph.nodes) == 11
    assert arc_kinds(graph) == {"ride": 14, "transfer": 6, "walk": 2}
    assert arcs_at(graph, "transfer") == {"B", "C", "F"}


def test_tm0_red_and_yellow_only_joined_by_the_walkway():
    """TM0: the only arcs between Red and Yellow nodes are the D-H walk arcs."""
    graph = build_graph(load_network(TOY_METRO))
    between = [(graph.nodes[i], graph.nodes[to], kind)
               for i, arcs in enumerate(graph.adj) for to, _, kind in arcs
               if {graph.nodes[i][1], graph.nodes[to][1]} == {"R1", "Y1"}]
    assert sorted(between) == [(("D", "R1"), ("H", "Y1"), "walk"),
                               (("H", "Y1"), ("D", "R1"), "walk")]


def test_tl0_branch_loop_counts():
    """TL0: 10 nodes and 20 arcs; transfer arcs only at J and C."""
    graph = build_graph(load_network(TOY_BRANCH_LOOP))
    assert len(graph.nodes) == 10
    assert sum(arc_kinds(graph).values()) == 20
    assert arc_kinds(graph)["transfer"] == 4
    assert arcs_at(graph, "transfer") == {"J", "C"}


def test_loop_closing_segment_is_an_arc():
    """The loop's last -> first hop (L4 -> C) is a ride arc in both directions."""
    graph = build_graph(load_network(TOY_BRANCH_LOOP))
    c, l4 = graph.node_of[("C", "V")], graph.node_of[("L4", "V")]
    assert (l4, 120, "ride") in graph.adj[c]
    assert (c, 120, "ride") in graph.adj[l4]


def test_nodes_are_sorted_and_indexed():
    """Nodes are numbered in sorted (station, service) order and node_of inverts nodes."""
    graph = build_graph(load_network(TOY_METRO))
    assert graph.nodes == sorted(graph.nodes)
    assert all(graph.node_of[node] == i for i, node in enumerate(graph.nodes))
    assert graph.station_nodes["C"] == [graph.node_of[("C", "B1")], graph.node_of[("C", "R1")]]


def test_closed_station_has_no_node():
    """[D1] A closed station gets no node, so its services are cut there."""
    graph = build_graph(close_stations(load_network(TOY_METRO), "C"))
    assert "C" not in graph.station_nodes
    assert len(graph.nodes) == 9
    assert arc_kinds(graph) == {"ride": 6, "transfer": 4, "walk": 2}


def test_transfer_times_follow_the_rules():
    """Default other-line 240 s, same-line 120 s, and an override wins both ways."""
    net = load_network(TOY_BRANCH_LOOP)
    assert transfer_time(net, "C", "O1", "V") == 240
    assert transfer_time(net, "J", "O1", "O2") == 120
    net = add_override(net, "C", "V", "O1", 60)
    assert transfer_time(net, "C", "O1", "V") == transfer_time(net, "C", "V", "O1") == 60


def test_no_transfer_pair_gets_no_arc():
    """Services listed in no_transfer never connect (like the two Magenta sections)."""
    net = load_network(TOY_METRO)
    net = replace(net, no_transfer=frozenset({frozenset({"R1", "B1"})}))
    assert arcs_at(build_graph(net), "transfer") == {"B", "F"}


def test_one_way_walkway_has_one_arc():
    """[D2] A one-way walkway only gets arcs from a to b."""
    net = load_network(TOY_METRO)
    net = replace(net, walkways=(replace(net.walkways[0], one_way=True),))
    assert arc_kinds(build_graph(net))["walk"] == 1


def test_build_is_deterministic_under_shuffling(tmp_path):
    """[D4] Shuffling the records in every file gives an identical graph."""
    expected = build_graph(load_network(TOY_METRO))
    for seed in range(10):
        folder = shuffled_copy(TOY_METRO, tmp_path / f"s{seed}", seed)
        assert build_graph(load_network(folder)) == expected
