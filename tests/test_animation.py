"""Route animation: geometry, the animator, the map controls and keys ([D58])."""

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QGraphicsScene

from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.main_window import MainWindow
from metro.ui.map_view import MapView, project
from metro.ui.route_animation import (
    MAX_MS,
    MIN_MS,
    RouteAnimator,
    cumulative_lengths,
    duration_ms,
    path_points,
    point_at,
    vertex_fractions,
)

TOY = load_network(TOY_METRO)
GRAPH = build_graph(TOY)


def toy_point(station: str) -> QPointF:
    """Scene position of a toy station, the same projection the map uses."""
    from metro.ui.map_view import projection_origin
    st = TOY.stations[station]
    return project(st.lat, st.lon, projection_origin(TOY))


def route(src, dst, criterion="fastest"):
    """A toy route."""
    return find_route(GRAPH, TOY, src, dst, criterion)


def line(*xy):
    """A polyline of points from (x, y) pairs."""
    return [QPointF(x, y) for x, y in xy]


# ---- geometry ----------------------------------------------------------------------------


def test_path_points_follow_the_stations_without_repeating_the_change():
    """TM2 A -> F rides A-B-C then C-E-F; the change at C appears once."""
    r = route("A", "F")
    stations = [s for leg in r.legs for s in leg.stations]
    assert stations.count("C") == 2
    points = path_points(r, toy_point)
    assert points[0] == toy_point("A") and points[-1] == toy_point("F")
    assert points.count(toy_point("C")) == 1
    assert len(points) == len(stations) - 1


def test_a_walk_between_rides_is_one_straight_segment():
    """TM11 A -> I: D and H are adjacent points, the walkway."""
    points = path_points(route("A", "I"), toy_point)
    d, h = points.index(toy_point("D")), points.index(toy_point("H"))
    assert h == d + 1


def test_cumulative_lengths_add_up():
    """A 3-4-5 triangle edge then a 4 unit edge."""
    assert cumulative_lengths(line((0, 0), (3, 4), (3, 8))) == [0.0, 5.0, 9.0]


@pytest.mark.parametrize("fraction, expected", [
    (0, (0, 0)), (0.25, (7.5, 0)), (0.5, (10, 5)), (0.75, (10, 12.5)), (1, (10, 20)),
    (-3, (0, 0)), (7, (10, 20)),
])
def test_point_at_interpolates_and_clamps(fraction, expected):
    """(0,0) -> (10,0) -> (10,20) is 30 long, so 0.25 is 7.5 along the first edge and 0.5 is
    15 along, 5 up the second; fractions outside 0..1 clamp to the ends."""
    pts = line((0, 0), (10, 0), (10, 20))
    got = point_at(pts, cumulative_lengths(pts), fraction)
    assert (got.x(), got.y()) == pytest.approx(expected)


def test_point_at_a_zero_length_path_is_the_first_point():
    """Two identical points have no length; no division by zero."""
    pts = line((4, 4), (4, 4))
    assert point_at(pts, cumulative_lengths(pts), 0.7) == pts[0]
    assert vertex_fractions(cumulative_lengths(pts)) == [0.0, 0.0]


def test_vertex_fractions_run_from_zero_to_one():
    """Stations lie at 0, 5/9 and 1 of the path."""
    fractions = vertex_fractions(cumulative_lengths(line((0, 0), (3, 4), (3, 8))))
    assert fractions == pytest.approx([0, 5 / 9, 1])


def test_duration_is_proportional_within_limits():
    """250 ms per hop, never under 3 s or over 15 s."""
    assert duration_ms(2) == MIN_MS and duration_ms(100) == MAX_MS
    assert duration_ms(21) == 5000


# ---- animator ----------------------------------------------------------------------------


@pytest.fixture
def animator(qtbot):
    """An animator on a bare scene, with toy positions."""
    scene = QGraphicsScene()
    anim = RouteAnimator(scene, toy_point)
    anim.scene_keepalive = scene  # the marker belongs to the scene; keep it alive with the test
    return anim


def test_before_a_route_it_is_hidden_and_inert(animator):
    """Play and step do nothing without a route."""
    assert not animator.marker.isVisible() and not animator.ready
    animator.play()
    animator.step(1)
    animator.advance(1000)
    assert not animator.playing and animator.fraction == 0


def test_a_new_route_puts_the_marker_at_its_start(animator):
    """Visible (once shown) and positioned on the first station."""
    animator.set_route(route("A", "F"))
    assert animator.ready and animator.marker.pos() == toy_point("A")
    assert animator.marker.isVisible()


def test_advance_moves_the_marker_along_the_path(animator):
    """After half the trip it is half way along the polyline."""
    r = route("A", "F")
    animator.set_route(r)
    total = duration_ms(len(animator.points))
    animator.advance(total // 2)
    expected = point_at(animator.points, animator.lengths, 0.5)
    assert animator.marker.pos() == expected and animator.fraction == pytest.approx(0.5)


def test_reaching_the_end_stops_and_announces(animator, qtbot):
    """playing_changed(False) arrives once, the marker rests on the last station."""
    animator.set_route(route("A", "F"))
    animator.play()
    seen = []
    animator.playing_changed.connect(seen.append)
    animator.advance(10 ** 6)
    assert not animator.playing and animator.fraction == 1.0 and seen == [False]
    assert animator.marker.pos() == toy_point("F")


def test_playing_again_after_the_end_starts_over(animator):
    """No need to press anything else to replay."""
    animator.set_route(route("A", "F"))
    animator.play()
    animator.advance(10 ** 6)
    animator.play()
    assert animator.playing and animator.fraction == 0.0


def test_pause_keeps_the_place_and_play_resumes_from_it(animator):
    """Pause then play continues; it does not restart."""
    animator.set_route(route("A", "F"))
    animator.play()
    animator.advance(500)
    here = animator.fraction
    animator.pause()
    assert not animator.playing and animator.fraction == here
    animator.play()
    assert animator.playing and animator.fraction == here


def test_toggle_alternates(animator):
    """Space does this."""
    animator.set_route(route("A", "F"))
    animator.toggle()
    assert animator.playing
    animator.toggle()
    assert not animator.playing


def test_the_state_signal_fires_only_on_a_change(animator):
    """Pausing while paused is silent."""
    animator.set_route(route("A", "F"))
    seen = []
    animator.playing_changed.connect(seen.append)
    animator.pause()
    animator.play()
    animator.play()
    animator.pause()
    assert seen == [True, False]


def test_step_forward_visits_each_station_in_order_then_stays_at_the_end(animator):
    """A -> F is Red A-B-C then Blue C-F: the path has four stations, so three steps reach F
    and a fourth changes nothing."""
    animator.set_route(route("A", "F"))
    visited = []
    for _ in range(3):
        animator.step(1)
        visited.append(animator.marker.pos())
    assert visited == [toy_point("B"), toy_point("C"), toy_point("F")]
    animator.step(1)
    assert animator.fraction == 1.0 and animator.marker.pos() == toy_point("F")


def test_step_backward_returns_through_the_stations_and_stops_at_the_start(animator):
    """From the end, three back-steps reach the start; one more stays."""
    animator.set_route(route("A", "F"))
    animator.advance(10 ** 6)
    for _ in range(3):
        animator.step(-1)
    assert animator.marker.pos() == toy_point("A") and animator.fraction == 0.0
    animator.step(-1)
    assert animator.fraction == 0.0


def test_step_pauses_a_running_animation(animator):
    """Stepping is for looking, so it stops the trip."""
    animator.set_route(route("A", "F"))
    animator.play()
    animator.step(1)
    assert not animator.playing


def test_a_new_route_stops_the_trip_and_resets(animator):
    """Changing routes mid-trip never leaves the old one running."""
    animator.set_route(route("A", "F"))
    animator.play()
    animator.advance(800)
    animator.set_route(route("A", "C"))
    assert not animator.playing and animator.fraction == 0.0
    assert animator.marker.pos() == toy_point("A")


def test_clear_hides_and_resets(animator):
    """With no route the marker is gone and nothing can play."""
    animator.set_route(route("A", "F"))
    animator.play()
    animator.clear()
    assert not animator.playing and not animator.marker.isVisible() and not animator.ready


def test_the_real_timer_advances_the_marker(animator, qtbot):
    """A short real wait moves the marker: the timer really calls advance."""
    animator.set_route(route("A", "F"))
    animator.play()
    qtbot.waitUntil(lambda: animator.fraction > 0, timeout=2000)
    animator.pause()
    stopped = animator.fraction
    qtbot.wait(100)
    assert animator.fraction == stopped


# ---- map and window -------------------------------------------------------------------------


@pytest.fixture
def toy_map(qtbot):
    """A shown map of toy_metro."""
    view = MapView(TOY)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    return view


def test_buttons_are_off_without_a_route_and_on_with_one(toy_map):
    """Play and step need a route."""
    c = toy_map.controls
    assert not c.play_button.isEnabled() and not c.step_button.isEnabled()
    toy_map.show_route(route("A", "F"))
    assert c.play_button.isEnabled() and c.step_button.isEnabled()
    toy_map.clear_route()
    assert not c.play_button.isEnabled() and not toy_map.animator.marker.isVisible()


def test_the_play_button_toggles_and_relabels_itself(toy_map, qtbot):
    """▶ becomes ❚❚ while playing, with the matching accessible name."""
    toy_map.show_route(route("A", "F"))
    button = toy_map.controls.play_button
    assert button.text() == "▶" and button.accessibleName() == "Play route animation"
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert toy_map.animator.playing
    assert button.text() == "❚❚" and button.accessibleName() == "Pause route animation"
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert not toy_map.animator.playing and button.text() == "▶"


def test_finishing_the_trip_resets_the_button(toy_map):
    """When the marker reaches the end the button offers Play again."""
    toy_map.show_route(route("A", "F"))
    toy_map.animator.play()
    toy_map.animator.advance(10 ** 6)
    assert toy_map.controls.play_button.text() == "▶"


def test_the_step_button_moves_to_the_next_station(toy_map, qtbot):
    """One click: the marker is on the second station of the route."""
    toy_map.show_route(route("A", "F"))
    qtbot.mouseClick(toy_map.controls.step_button, Qt.MouseButton.LeftButton)
    assert toy_map.animator.marker.pos() == toy_point("B")


def test_keys_play_and_step(toy_map, qtbot):
    """Space toggles, . steps forward, , steps back."""
    toy_map.show_route(route("A", "F"))
    qtbot.keyClick(toy_map, Qt.Key.Key_Space)
    assert toy_map.animator.playing
    qtbot.keyClick(toy_map, Qt.Key.Key_Space)
    assert not toy_map.animator.playing
    qtbot.keyClick(toy_map, Qt.Key.Key_Period)
    qtbot.keyClick(toy_map, Qt.Key.Key_Period)
    assert toy_map.animator.marker.pos() == toy_point("C")
    qtbot.keyClick(toy_map, Qt.Key.Key_Comma)
    assert toy_map.animator.marker.pos() == toy_point("B")


def test_keys_do_nothing_without_a_route(toy_map, qtbot):
    """Space on an empty map is harmless."""
    qtbot.keyClick(toy_map, Qt.Key.Key_Space)
    qtbot.keyClick(toy_map, Qt.Key.Key_Period)
    assert not toy_map.animator.playing


def test_the_marker_is_not_dimmed_cleared_or_counted_as_overlay(toy_map):
    """It lives outside network_items and overlay.items, so dimming and clearing skip it."""
    marker = toy_map.animator.marker
    toy_map.show_route(route("A", "F"))
    assert marker not in toy_map.network_items and marker not in toy_map.overlay.items
    assert marker.opacity() == 1.0 and marker.zValue() > max(
        i.zValue() for i in toy_map.overlay.items)


def test_a_theme_change_during_a_trip_keeps_it_going(toy_map):
    """Redrawing the route in new colours must not stop or move the marker."""
    from metro.ui.theme import DARK
    toy_map.show_route(route("A", "F"))
    toy_map.animator.play()
    toy_map.animator.advance(600)
    where = toy_map.animator.marker.pos()
    toy_map.set_theme(DARK)
    assert toy_map.animator.playing and toy_map.animator.marker.pos() == where


def test_window_shows_the_marker_for_a_found_route_and_hides_it_on_reset(qtbot):
    """End to end through MainWindow."""
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    window.on_map_click("A")
    window.on_map_click("F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert window.map.animator.ready and window.map.controls.play_button.isEnabled()
    window.reset()
    assert not window.map.animator.ready and not window.map.controls.play_button.isEnabled()


def test_switching_alternatives_restarts_the_marker_on_the_new_route(qtbot):
    """Each route has its own path; the marker follows the one on screen."""
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    window.on_map_click("A")
    window.on_map_click("F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    window.map.animator.advance(500)
    window.route_panel.tabs.setCurrentIndex(1)
    assert window.map.animator.fraction == 0.0
    assert len(window.map.animator.points) == len(
        {s for leg in window.state.route.legs for s in leg.stations})


def test_real_network_trip_duration_follows_the_stop_count(qtbot):
    """A 30-stop journey takes 30 x 250 ms = 7.5 s."""
    network = load_network(REAL_DATA)
    graph = build_graph(network)
    by_name = {s.name: i for i, s in network.stations.items()}
    r = find_route(graph, network, by_name["Samaypur Badli"], by_name["Noida City Centre"])
    view = MapView(network)
    qtbot.addWidget(view)
    scene = QGraphicsScene()
    anim = RouteAnimator(scene, view.point_of)
    anim.set_route(r)
    assert anim.ready and len(anim.points) == r.stops + 1
    assert duration_ms(len(anim.points)) == 7500
