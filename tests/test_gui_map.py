"""Map view tests with pytest-qt (T22–T24; FR9–FR12, ER11, ER12, [D21])."""

import math

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.map_view import MAX_ZOOM, MIN_ZOOM, MapView, label_tier


@pytest.fixture
def toy_map(qtbot):
    """A shown 800 x 600 map of toy_metro."""
    view = MapView(load_network(TOY_METRO))
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    return view


def wheel(view, delta: int) -> None:
    """Send one wheel event with the given vertical angle delta to the viewport centre."""
    centre = QPointF(view.viewport().width() / 2, view.viewport().height() / 2)
    event = QWheelEvent(centre, view.mapToGlobal(centre.toPoint()).toPointF(), QPoint(0, 0),
                        QPoint(0, delta), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(event)


def test_t22_zoom_is_clamped(toy_map):
    """T22: zooming far in or out stops at 20x and 0.2x the fit scale."""
    for _ in range(100):
        wheel(toy_map, 120)
    assert toy_map.zoom() == pytest.approx(MAX_ZOOM)
    for _ in range(200):
        wheel(toy_map, -120)
    assert toy_map.zoom() == pytest.approx(MIN_ZOOM)


def test_t22_zero_wheel_delta_is_ignored(toy_map):
    """ER11: a zero delta changes nothing."""
    before = toy_map.zoom()
    wheel(toy_map, 0)
    assert toy_map.zoom() == before


def test_keyboard_zoom_and_fit(toy_map, qtbot):
    """+ zooms in, - zooms out and 0 fits the network again."""
    qtbot.keyClick(toy_map, Qt.Key.Key_Plus)
    assert toy_map.zoom() == pytest.approx(1.15)
    qtbot.keyClick(toy_map, Qt.Key.Key_Minus)
    qtbot.keyClick(toy_map, Qt.Key.Key_Minus)
    assert toy_map.zoom() < 1
    qtbot.keyClick(toy_map, Qt.Key.Key_0)
    assert toy_map.zoom() == pytest.approx(1.0)


def test_t23_zero_size_viewport_is_safe(toy_map):
    """T23: resizing to 0 x 0 and asking for a fit neither crashes nor changes the view."""
    toy_map.resize(0, 0)
    before = toy_map.transform()
    toy_map.fit_all()
    route = find_route(build_graph(toy_map.network), toy_map.network, "A", "F")
    toy_map.show_route(route)
    assert toy_map.transform() == before
    assert all(math.isfinite(v) for v in (before.m11(), before.m22()))


def test_t24_overlapping_stations_all_listed_nearest_first(qtbot):
    """T24: when markers overlap, the tooltip lists every station, nearest first."""
    view = MapView(load_network(REAL_DATA))
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    view.zoom_by(MIN_ZOOM)  # zoomed far out, Paschim Vihar East and West overlap
    east = view.mapFromScene(view.point_of("PMVR"))
    near = view.stations_near(east)
    assert near[0] == "PMVR" and "PMVA" in near
    text = view.tooltip_at(east)
    assert text.index("Paschim Vihar (East)") < text.index("Paschim Vihar (West)")


def test_click_emits_station(toy_map, qtbot):
    """FR4: clicking a marker emits station_clicked with its ID."""
    pos = toy_map.mapFromScene(toy_map.point_of("C"))
    with qtbot.waitSignal(toy_map.station_clicked) as blocker:
        qtbot.mouseClick(toy_map.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert blocker.args == ["C"]


def test_route_overlay_dims_and_clears(toy_map):
    """FR10: showing a route dims the network to 25%; clearing restores it."""
    route = find_route(build_graph(toy_map.network), toy_map.network, "A", "I")
    toy_map.show_route(route)
    assert toy_map.network_items[0].opacity() == pytest.approx(0.25)
    assert len(toy_map.overlay.items) > 0
    toy_map.clear_route()
    assert toy_map.overlay.items == []
    assert toy_map.network_items[0].opacity() == 1.0


def test_label_level_of_detail(toy_map):
    """[D21] Zoomed out shows interchange labels only; zoomed in shows every label."""
    assert [label_tier(z) for z in (1, 3, 10)] == [0, 1, 2]
    assert toy_map.labels["C"].isVisible() and not toy_map.labels["E"].isVisible()
    toy_map.zoom_by(10)
    assert toy_map.labels["E"].isVisible()
