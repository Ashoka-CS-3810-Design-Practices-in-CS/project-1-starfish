"""Label overlap suppression and the floating map controls ([D50], [D51])."""

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import QRectF, Qt

from metro.data import load_network
from metro.ui.map_labels import declutter, eligible, importance
from metro.ui.map_view import MapView


def rect(x, y, w=60, h=14):
    """A label rectangle."""
    return QRectF(x, y, w, h)


def test_declutter_keeps_the_first_of_two_overlapping_labels():
    """Candidates come in order of importance; the later overlapping one is dropped."""
    assert declutter([("hub", rect(0, 0)), ("minor", rect(30, 5))]) == {"hub"}


def test_declutter_keeps_labels_that_do_not_overlap():
    """Separate labels all stay, even in the same grid cell."""
    labels = [("a", rect(0, 0)), ("b", rect(0, 30)), ("c", rect(100, 0))]
    assert declutter(labels) == {"a", "b", "c"}


def test_declutter_pads_labels_so_they_do_not_touch():
    """Two labels 1 px apart count as colliding (padding is 2 px each)."""
    assert declutter([("a", rect(0, 0)), ("b", rect(61, 0))]) == {"a"}


def test_declutter_finds_collisions_across_grid_cells():
    """A wide label overlaps a neighbour that starts in a different 64 px cell."""
    assert declutter([("wide", rect(0, 0, 200)), ("late", rect(150, 2))]) == {"wide"}


def test_declutter_is_order_dependent_by_design():
    """Swapping the importance order swaps the winner."""
    a, b = ("a", rect(0, 0)), ("b", rect(10, 0))
    assert declutter([a, b]) == {"a"} and declutter([b, a]) == {"b"}


def test_importance_orders_interchange_then_terminal_then_rest():
    """The ID only breaks ties inside a group."""
    ranked = sorted(["z", "t", "i", "a"], key=lambda s: importance(s, {"i"}, {"t"}))
    assert ranked == ["i", "t", "a", "z"]


def test_eligible_follows_the_zoom_tier():
    """Tier 0 shows interchanges, tier 1 adds terminals, tier 2 everything."""
    hub, end, other = "hub", "end", "other"
    args = ({hub}, {end})
    assert [eligible(0, s, *args) for s in (hub, end, other)] == [True, False, False]
    assert [eligible(1, s, *args) for s in (hub, end, other)] == [True, True, False]
    assert [eligible(2, s, *args) for s in (hub, end, other)] == [True, True, True]


@pytest.fixture
def real_map(qtbot):
    """A shown 1000 x 700 map of the real network."""
    view = MapView(load_network(REAL_DATA))
    qtbot.addWidget(view)
    view.resize(1000, 700)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    return view


def visible_rects(view):
    """View-pixel rectangles of every visible label."""
    return [view.label_rect(sid) for sid, label in view.labels.items() if label.isVisible()]


@pytest.mark.parametrize("zoom", [1, 2, 3, 5, 8])
def test_no_two_visible_labels_overlap(real_map, zoom):
    """At any zoom, the labels left visible do not overlap each other."""
    real_map.zoom_by(zoom)
    rects = visible_rects(real_map)
    assert rects
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not a.intersects(b)


def test_decluttering_hides_labels_in_the_dense_centre_but_not_everywhere(real_map):
    """Fully zoomed in on a dense area still hides some labels; far fewer than all are shown."""
    real_map.zoom_by(5)
    shown = sum(label.isVisible() for label in real_map.labels.values())
    assert 0 < shown < len(real_map.labels)


def test_more_labels_appear_as_the_user_zooms_in(real_map):
    """Zooming in makes room: the visible count never drops from 3x to 8x."""
    counts = []
    for zoom in (3, 8 / 3):
        real_map.zoom_by(zoom)
        counts.append(sum(label.isVisible() for label in real_map.labels.values()))
    assert counts[1] >= counts[0]


def test_panning_does_not_change_which_labels_show(real_map, qtbot):
    """Overlap depends only on distances between labels, so a pan keeps the same set."""
    real_map.zoom_by(5)
    before = {sid for sid, label in real_map.labels.items() if label.isVisible()}
    real_map.horizontalScrollBar().setValue(real_map.horizontalScrollBar().value() + 120)
    real_map.update_labels()
    assert {sid for sid, label in real_map.labels.items() if label.isVisible()} == before


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


def test_controls_sit_in_the_top_right_corner(toy_map):
    """The control column is fully inside the view, 12 px from the top and right edges."""
    controls = toy_map.controls
    assert controls.isVisible()
    assert controls.y() == 12
    assert toy_map.width() - (controls.x() + controls.width()) == 12
    toy_map.resize(500, 400)
    assert toy_map.width() - (controls.x() + controls.width()) == 12


def test_zoom_in_button_zooms_in_by_one_step(toy_map, qtbot):
    """The + button does what the + key does."""
    qtbot.mouseClick(toy_map.controls.zoom_in_button, Qt.MouseButton.LeftButton)
    assert toy_map.zoom() == pytest.approx(1.15)


def test_zoom_out_button_zooms_out_by_one_step(toy_map, qtbot):
    """The − button does what the - key does."""
    qtbot.mouseClick(toy_map.controls.zoom_out_button, Qt.MouseButton.LeftButton)
    assert toy_map.zoom() == pytest.approx(1 / 1.15)


def test_fit_button_restores_the_whole_network(toy_map, qtbot):
    """After zooming in a lot, Fit shows the whole network again."""
    toy_map.zoom_by(8)
    qtbot.mouseClick(toy_map.controls.fit_button, Qt.MouseButton.LeftButton)
    assert toy_map.zoom() == pytest.approx(1.0)


def test_controls_have_names_and_tooltips_and_do_not_steal_focus_by_click(toy_map):
    """[D20] Every button is named; clicking never moves the keyboard focus off the map."""
    for button in (toy_map.controls.zoom_in_button, toy_map.controls.zoom_out_button,
                   toy_map.controls.fit_button):
        assert button.accessibleName() and button.toolTip()
        assert button.focusPolicy() == Qt.FocusPolicy.TabFocus


def test_clicking_a_control_does_not_choose_a_station_under_it(toy_map, qtbot):
    """A click on a button must not reach the map as a station click."""
    clicks = []
    toy_map.station_clicked.connect(clicks.append)
    qtbot.mouseClick(toy_map.controls.fit_button, Qt.MouseButton.LeftButton)
    assert clicks == []
