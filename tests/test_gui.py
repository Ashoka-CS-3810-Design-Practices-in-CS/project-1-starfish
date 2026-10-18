"""Main-window tests with pytest-qt (T25–T28; FR4, FR13, FR15, ER1, ER13, ER14, ER17)."""

import time

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import Qt

from metro.app_state import MSG_FAILED, MSG_UNEXPECTED
from metro.data import load_network
from metro.errors import RouteCancelled
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.main_window import MainWindow


def make_window(qtbot, folder=TOY_METRO, find=find_route, watchdog_ms=2000) -> MainWindow:
    """A shown main window on a dataset, optionally with a fake search function."""
    network = load_network(folder)
    window = MainWindow(network, build_graph(network), find, watchdog_ms)
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    return window


def slow_find(delays: dict[str, float]):
    """A find_route that sleeps `delays[src]` seconds first, respecting the cancel event."""
    def find(graph, network, src, dst, criterion, cancel):
        end = time.monotonic() + delays.get(src, 0)
        while time.monotonic() < end:
            if cancel.is_set():
                raise RouteCancelled()
            time.sleep(0.005)
        return find_route(graph, network, src, dst, criterion, cancel)
    return find


def choose(window: MainWindow, source: str, destination: str) -> None:
    """Pick two stations through the map-click path."""
    window.on_map_click(source)
    window.on_map_click(destination)


def test_full_workflow_shows_route(qtbot):
    """Choosing two stations starts a search automatically and shows the route (FR6, FR7)."""
    window = make_window(qtbot)
    choose(window, "A", "F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert window.route_panel.summary.text() == "Estimated 12 min · 1 interchange · 3 stops"
    assert window.route_panel.rows.count() == 3  # leg, change, leg
    assert window.map.overlay.items


def test_t25_stale_result_is_discarded(qtbot):
    """T25 (ER14): a slow first request finishing after a newer one is ignored."""
    window = make_window(qtbot, find=slow_find({"A": 0.6}))
    choose(window, "A", "F")  # slow request
    window.on_map_click("E")  # third click: new source E, destination cleared
    window.on_map_click("F")  # fast request E -> F
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    qtbot.wait(800)  # long enough for the slow result to arrive if it were not cancelled
    assert window.state.route.source == "E"


def test_t26_watchdog_then_retry(qtbot):
    """T26 (ER13): a search that never finishes fails after the watchdog; Retry works."""
    delays = {"A": 60}
    window = make_window(qtbot, find=slow_find(delays), watchdog_ms=200)
    choose(window, "A", "F")
    qtbot.waitUntil(lambda: window.state.message == MSG_FAILED, timeout=3000)
    assert window.banner.isVisible() and window.banner.button.text() == "Retry"
    assert (window.state.source, window.state.destination) == ("A", "F")
    delays["A"] = 0
    qtbot.mouseClick(window.banner.button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")


def test_unexpected_error_keeps_selection(qtbot):
    """ER17: an exception in the worker gives a short message; the selection is kept."""
    def broken(*args):
        raise ValueError("boom")
    window = make_window(qtbot, find=broken)
    choose(window, "A", "F")
    qtbot.waitUntil(lambda: window.state.message == MSG_UNEXPECTED)
    assert (window.state.source, window.state.destination) == ("A", "F")
    assert "boom" not in window.banner.text.text()


@pytest.mark.parametrize("use_key", [False, True])
def test_t27_reset_by_button_and_escape(qtbot, use_key):
    """T27 (FR13): Reset (button or Esc) cancels work and clears everything."""
    window = make_window(qtbot, find=slow_find({"A": 0.5}))
    choose(window, "A", "F")
    assert window.state.computing
    if use_key:
        qtbot.keyClick(window, Qt.Key.Key_Escape)
    else:
        qtbot.mouseClick(window.reset_button, Qt.MouseButton.LeftButton)
    assert window.state.phase == "Idle"
    qtbot.wait(700)  # the cancelled search must not bring a route back
    assert window.state.route is None
    assert window.from_box.field.text() == "" and window.to_box.field.text() == ""


def test_t28_keyboard_only_route(qtbot):
    """T28: type, arrow down, Enter in both fields; the route appears without the mouse."""
    window = make_window(qtbot, folder=REAL_DATA)
    window.from_box.field.setFocus()
    qtbot.keyClicks(window.from_box.field, "Rajiv Chowk")
    qtbot.keyClick(window.from_box.field, Qt.Key.Key_Down)
    qtbot.keyClick(window.from_box.field, Qt.Key.Key_Return)
    assert window.from_box.field.text() == "Rajiv Chowk"
    window.to_box.field.setFocus()
    qtbot.keyClicks(window.to_box.field, "hauz kas")  # a typo
    assert window.to_box.list.item(0).text() == "Did you mean …?"
    qtbot.keyClick(window.to_box.field, Qt.Key.Key_Down)
    qtbot.keyClick(window.to_box.field, Qt.Key.Key_Return)
    assert window.to_box.field.text() == "Hauz Khas"
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert window.route_panel.summary.text().startswith("Estimated 22 min · 0 interchanges")


def test_escape_closes_suggestions_before_resetting(qtbot):
    """Esc with an open list only closes the list; the chosen source stays."""
    window = make_window(qtbot)
    window.on_map_click("A")
    window.to_box.field.setFocus()
    qtbot.keyClicks(window.to_box.field, "Station")
    assert window.to_box.list_is_open()
    qtbot.keyClick(window.to_box.field, Qt.Key.Key_Escape)
    assert not window.to_box.list_is_open() and window.state.source == "A"


def test_no_match_and_missing_hints(qtbot):
    """ER2 and ER1 hints appear under the right field; Find is disabled with a reason."""
    window = make_window(qtbot)
    qtbot.keyClicks(window.from_box.field, "xyz")
    assert window.from_box.hint.text() == "No station matches 'xyz'."
    window.from_box.field.clear()
    window.on_map_click("A")
    assert window.to_box.hint.text() == "Select a source and a destination station."
    assert not window.find_button.isEnabled()
    assert window.find_button.toolTip() == "Select a source and a destination station."


def test_swap_recomputes(qtbot):
    """Swap exchanges the fields and recomputes (Alt+W)."""
    window = make_window(qtbot)
    choose(window, "A", "F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    qtbot.keyClick(window, Qt.Key.Key_W, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(lambda: window.state.route is not None and window.state.route.source == "F")
    assert window.from_box.field.text() == "Station F"


def test_no_route_banner_offers_reset(qtbot, broken_dataset):
    """ER7: no route shows an info banner with a Reset button."""
    window = make_window(qtbot, folder=broken_dataset("disconnected"))
    choose(window, "H", "A")
    qtbot.waitUntil(lambda: window.state.phase == "NoRoute")
    assert window.banner.button.text() == "Reset"


def test_narrow_window_hides_panel(qtbot):
    """Below 1100 px the side panel collapses behind a toggle."""
    window = make_window(qtbot)
    window.resize(1000, 700)
    qtbot.waitUntil(lambda: not window.panel.isVisible())
    assert window.panel_toggle.isVisible()
    window.panel_toggle.click()
    assert window.panel.isVisible()


def test_escape_in_a_field_resets(qtbot):
    """Esc typed into a field with no list open reaches the window and resets."""
    window = make_window(qtbot)
    choose(window, "A", "F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    qtbot.keyClick(window.to_box.field, Qt.Key.Key_Escape)
    assert window.state.phase == "Idle"


def test_startup_error_text_lists_problems(broken_dataset):
    """ER9: the start-up dialog text gives the count, the problems and the folder."""
    import main
    from metro.errors import DataError
    folder = broken_dataset("multi_defect")
    with pytest.raises(DataError) as info:
        load_network(folder)
    text = main.problems_text(info.value, folder)
    assert text.startswith("The network data has 4 problems.")
    assert text.endswith(f"Data folder: {folder}")
