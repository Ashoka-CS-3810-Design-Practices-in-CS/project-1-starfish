"""Route overlay details: station dots, change badges and crisp route stations (FR10, FR11)."""

import pytest
from conftest import REAL_DATA, TOY_METRO

from metro.data import load_network
from metro.describe import interchange_badge_text
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.map_view import MapView


@pytest.fixture
def toy_map(qtbot):
    """A shown 800 x 600 map of toy_metro, with its graph."""
    network = load_network(TOY_METRO)
    view = MapView(network)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    view.graph = build_graph(network)
    return view


def route_of(view, src, dst, criterion="fastest"):
    """The route between two stations of the map's network."""
    return find_route(view.graph, view.network, src, dst, criterion)


def test_every_station_on_the_route_gets_one_dot(toy_map):
    """TM2 A -> F: one dot per distinct station over all legs."""
    route = route_of(toy_map, "A", "F")
    toy_map.show_route(route)
    stations = {s for leg in route.legs for s in leg.stations}
    assert len(toy_map.overlay.dots) == len(stations)
    positions = {(round(d.pos().x(), 3), round(d.pos().y(), 3)) for d in toy_map.overlay.dots}
    assert positions == {(round(toy_map.point_of(s).x(), 3), round(toy_map.point_of(s).y(), 3))
                         for s in stations}


def test_dots_sit_above_the_route_line_and_the_dimmed_network(toy_map):
    """Dots (z 5.5) are above route lines (z 5) and the network (z <= 3)."""
    toy_map.show_route(route_of(toy_map, "A", "F"))
    assert all(d.zValue() > 5 for d in toy_map.overlay.dots)


def test_a_change_gets_a_labelled_badge(toy_map):
    """TM2 changes at C: one badge reading '⇄ Change at Station C', at C."""
    route = route_of(toy_map, "A", "F")
    toy_map.show_route(route)
    (badge,) = toy_map.overlay.badges
    assert badge.text() == "⇄ Change at Station C"
    assert badge.pos() == toy_map.point_of("C")
    assert badge.zValue() > max(d.zValue() for d in toy_map.overlay.dots)


def test_a_walk_change_is_labelled_with_both_stations_and_ringed_twice(toy_map):
    """TM11 A -> I walks from D to H between two rides."""
    route = route_of(toy_map, "A", "I")
    toy_map.show_route(route)
    (badge,) = toy_map.overlay.badges
    assert badge.text() == "⇄ Walk Station D → Station H"
    rings = [i for i in toy_map.overlay.items if i.zValue() == 6.5]
    assert len(rings) == 2


def test_a_route_without_changes_has_dots_but_no_badge(toy_map):
    """TM3 A -> C is one Red leg."""
    toy_map.show_route(route_of(toy_map, "A", "C"))
    assert toy_map.overlay.badges == [] and toy_map.overlay.dots


def test_neighbouring_badges_alternate_above_and_below(qtbot):
    """On a route with several changes the label offsets alternate, so labels rarely collide."""
    network = load_network(REAL_DATA)
    view = MapView(network)
    qtbot.addWidget(view)
    view.resize(900, 700)
    view.show()
    qtbot.waitExposed(view)
    graph = build_graph(network)
    by_name = {s.name: i for i, s in network.stations.items()}
    route = find_route(graph, network, by_name["Samaypur Badli"], by_name["Noida City Centre"],
                       "fewest_stops")
    assert len(route.interchanges) >= 2
    view.show_route(route)
    offsets = [b.transform().dy() for b in view.overlay.badges]
    assert offsets[0] != offsets[1]


def test_clearing_the_route_removes_dots_and_badges(toy_map):
    """The scene returns to its size before the route was drawn."""
    before = len(toy_map.scene().items())
    toy_map.show_route(route_of(toy_map, "A", "F"))
    assert len(toy_map.scene().items()) > before
    toy_map.clear_route()
    assert len(toy_map.scene().items()) == before
    assert toy_map.overlay.dots == [] and toy_map.overlay.badges == []


def test_showing_a_second_route_replaces_the_first(toy_map):
    """Switching routes (alternatives) never leaves dots or badges of the old one behind."""
    toy_map.show_route(route_of(toy_map, "A", "F"))
    count = len(toy_map.scene().items())
    toy_map.show_route(route_of(toy_map, "A", "F"))
    assert len(toy_map.scene().items()) == count


def test_route_stations_stay_crisp_and_the_rest_dim(toy_map):
    """The route's markers and labels are at full opacity; others at 25%."""
    route = route_of(toy_map, "A", "C")
    toy_map.show_route(route)
    on_route = {s for leg in route.legs for s in leg.stations}
    for sid in toy_map.network.stations:
        expected = 1.0 if sid in on_route else 0.25
        assert toy_map.markers[sid].opacity() == pytest.approx(expected)
        assert toy_map.labels[sid].opacity() == pytest.approx(expected)
    toy_map.clear_route()
    assert all(m.opacity() == 1.0 for m in toy_map.markers.values())


def test_badge_text_helper(toy_map):
    """The text comes from describe, so it can be tested without Qt."""
    route = route_of(toy_map, "A", "F")
    assert interchange_badge_text(toy_map.network, route.interchanges[0]) == \
        "⇄ Change at Station C"
