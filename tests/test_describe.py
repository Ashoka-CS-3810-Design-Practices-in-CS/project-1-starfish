"""Tests for the route text helpers: station lists and export (FR7, FR8, optional features)."""

import pytest
from conftest import REAL_DATA, TOY_METRO

from metro.data import load_network
from metro.describe import (
    between_names,
    export_route_text,
    leg_station_names,
    route_lines,
    route_steps,
)
from metro.graph import build_graph
from metro.models import Interchange, Leg
from metro.router import find_route


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


def test_route_steps_put_each_change_between_two_rides(toy):
    """TM2 A -> F is Red, change at C, Blue: leg, interchange, leg."""
    network, graph = toy
    route = find_route(graph, network, "A", "F")
    kinds = [type(step) for step in route_steps(route)]
    assert kinds == [Leg, Interchange, Leg]


def test_route_steps_keep_walks_at_the_ends_without_a_change(toy):
    """TM10 A -> H ends with a WALK leg and has no interchange."""
    network, graph = toy
    route = find_route(graph, network, "A", "H")
    assert [type(step) for step in route_steps(route)] == [Leg, Leg]
    assert route_steps(route)[-1].kind == "WALK"


def test_leg_station_names_are_in_travel_order(real):
    """Rajiv Chowk -> Hauz Khas is one Yellow leg that starts and ends at those stations."""
    network, graph = real
    route = find_route(graph, network, *station_ids(network, "Rajiv Chowk", "Hauz Khas"))
    (leg,) = route.legs
    names = leg_station_names(network, leg)
    assert names[0] == "Rajiv Chowk" and names[-1] == "Hauz Khas"
    assert len(names) == len(leg.stations) == route.stops + 1
    assert between_names(network, leg) == names[1:-1]


def test_a_walk_leg_has_nothing_in_between(toy):
    """A two-station WALK leg lists no intermediate stations."""
    network, graph = toy
    walk = find_route(graph, network, "A", "H").legs[-1]
    assert between_names(network, walk) == []


def test_route_lines_expand_lists_intermediate_stations(real):
    """Expanded lines have one '· name' row per station passed through, under their leg."""
    network, graph = real
    route = find_route(graph, network, *station_ids(network, "Rajiv Chowk", "Hauz Khas"))
    plain = route_lines(network, route)
    expanded = route_lines(network, route, expand=True)
    inside = between_names(network, route.legs[0])
    assert expanded[:2] == plain[:2]
    assert expanded[2:] == [f"     · {name}" for name in inside]
    assert len(inside) == route.stops - 1


def test_export_txt_has_title_summary_and_stations(real):
    """The text export starts with the title and lists the stations in between."""
    network, graph = real
    route = find_route(graph, network, *station_ids(network, "Rajiv Chowk", "Hauz Khas"))
    text = export_route_text(network, route)
    lines = text.splitlines()
    assert lines[0] == "Rajiv Chowk → Hauz Khas"
    assert lines[1].startswith("Estimated ") and "0 interchanges" in lines[1]
    assert "     · " + between_names(network, route.legs[0])[0] in lines
    assert text.endswith("\n")


def test_export_markdown_structure(toy):
    """The Markdown export has a heading, a bold summary, and the change as its own paragraph."""
    network, graph = toy
    route = find_route(graph, network, "A", "F")
    text = export_route_text(network, route, format="md")
    lines = text.splitlines()
    assert lines[0] == "# Station A → Station F"
    assert lines[2] == "**Estimated 12 min · 1 interchange · 3 stops**"
    assert "*⇒ Change at Station C (4 min)*" in lines
    assert any(line.startswith("1. Red Line") for line in lines)
    assert any(line.startswith("2. Blue Line") for line in lines)


def test_export_unknown_format_is_rejected(toy):
    """Only 'txt' and 'md' exist."""
    network, graph = toy
    route = find_route(graph, network, "A", "F")
    with pytest.raises(ValueError, match="Unknown export format 'pdf'"):
        export_route_text(network, route, format="pdf")


def station_ids(network, *names):
    """Station IDs for exact display names."""
    by_name = {st.name: sid for sid, st in network.stations.items()}
    return [by_name[name] for name in names]
