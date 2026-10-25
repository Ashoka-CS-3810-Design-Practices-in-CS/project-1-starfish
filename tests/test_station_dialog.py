"""Station card: core facts, the dialog, the map's context menu and Ctrl+I ([D54])."""

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import Qt

from metro.data import load_network
from metro.describe import coordinates_text, station_details
from metro.graph import build_graph
from metro.ui.main_window import MainWindow
from metro.ui.map_view import MapView
from metro.ui.station_dialog import StationDialog, luminance, text_colour_on

TOY = load_network(TOY_METRO)
REAL = load_network(REAL_DATA)
BY_NAME = {s.name: i for i, s in REAL.stations.items()}


# ---- core ------------------------------------------------------------------------------


def test_details_of_an_interchange():
    """Rajiv Chowk is on Blue and Yellow, an interchange, and not a terminal."""
    d = station_details(REAL, BY_NAME["Rajiv Chowk"])
    assert [name for name, _ in d.lines] == ["Blue Line", "Yellow Line"]
    assert d.interchange_note == "Interchange between Blue Line, Yellow Line"
    assert d.terminal_of == () and "Connaught Place" in d.aliases
    assert d.neighbours == ("Barakhamba", "New Delhi", "Patel Chowk", "RK Ashram Marg")


def test_details_of_a_terminal_that_is_also_an_interchange():
    """Dwarka Sector 21: Blue Line terminal and Airport Express interchange."""
    d = station_details(REAL, BY_NAME["Dwarka Sector 21"])
    assert d.terminal_of == ("Blue Line",)
    assert d.interchange_note.startswith("Interchange between")


def test_details_of_a_branch_change_names_the_line_once():
    """Yamuna Bank has one line but two services, so it is a branch change."""
    d = station_details(REAL, BY_NAME["Yamuna Bank"])
    assert [n for n, _ in d.lines] == ["Blue Line"]
    assert d.interchange_note == "Change between trains of the Blue Line (branch)"


def test_details_of_a_plain_station_have_no_interchange_note():
    """In toy_metro, A is a Red terminal with one neighbour and no other service."""
    d = station_details(TOY, "A")
    assert d.interchange_note == "" and d.terminal_of == ("Red Line",)
    assert d.neighbours == ("Station B",)


def test_coordinates_use_hemisphere_letters():
    """Positive latitude is N and longitude E; negatives flip."""
    assert coordinates_text(28.6329, 77.2196) == "28.6329° N, 77.2196° E"
    assert coordinates_text(-33.8688, -70.5) == "33.8688° S, 70.5000° W"


def test_text_colour_picks_the_higher_contrast():
    """Yellow gets black text, dark blue gets white; black/white themselves are extremes."""
    assert text_colour_on("#E8B100") == "#000000"
    assert text_colour_on("#1E5AA8") == "#FFFFFF"
    assert luminance("#000000") == 0 and luminance("#FFFFFF") == pytest.approx(1)
    for line in REAL.lines.values():  # every real line colour gets at least 4.5:1
        bg = luminance(line.color)
        fg = luminance(text_colour_on(line.color))
        assert (max(bg, fg) + 0.05) / (min(bg, fg) + 0.05) >= 4.5, line.name


# ---- dialog ----------------------------------------------------------------------------


def test_dialog_shows_name_code_and_a_tag_per_line(qtbot):
    """The card names the station, its code and each line in words."""
    dialog = StationDialog(REAL, BY_NAME["Rajiv Chowk"])
    qtbot.addWidget(dialog)
    assert dialog.title.text() == "Rajiv Chowk"
    assert [t.text() for t in dialog.tags] == ["Blue Line", "Yellow Line"]
    texts = [lbl.text() for lbl in dialog.findChildren(type(dialog.title))]
    assert "Code: RJCK" in texts and any(t.startswith("Interchange between") for t in texts)
    assert any(t.startswith("Position: 28.6329° N") for t in texts)


def test_dialog_buttons_emit_and_close(qtbot):
    """Set as From and Set as To pass the station on and close the card."""
    dialog = StationDialog(TOY, "C")
    qtbot.addWidget(dialog)
    dialog.show()
    with qtbot.waitSignal(dialog.set_as_from) as blocker:
        dialog.from_button.click()
    assert blocker.args == ["C"] and not dialog.isVisible()
    dialog = StationDialog(TOY, "C")
    qtbot.addWidget(dialog)
    dialog.show()
    with qtbot.waitSignal(dialog.set_as_to) as blocker:
        dialog.to_button.click()
    assert blocker.args == ["C"]


def test_a_closed_station_cannot_be_chosen_from_the_card(qtbot):
    """ER6: the buttons are off, with a reason, and the card says the station is closed."""
    from conftest import close_stations
    dialog = StationDialog(close_stations(TOY, "C"), "C")
    qtbot.addWidget(dialog)
    assert not dialog.from_button.isEnabled() and not dialog.to_button.isEnabled()
    assert dialog.from_button.toolTip() == "A closed station cannot be used."
    assert any(lbl.text() == "This station is closed." for lbl in dialog.findChildren(
        type(dialog.title)))


# ---- map menu --------------------------------------------------------------------------


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


def test_menu_for_one_station_has_three_actions_that_emit(toy_map):
    """Details, Set as From and Set as To, each emitting (action, station)."""
    menu = toy_map.build_station_menu(["C"])
    assert [a.text() for a in menu.actions()] == ["Station details…", "Set as From", "Set as To"]
    seen = []
    toy_map.station_action.connect(lambda action, sid: seen.append((action, sid)))
    for action in menu.actions():
        action.trigger()
    assert seen == [("details", "C"), ("from", "C"), ("to", "C")]


def test_menu_for_overlapping_stations_has_a_submenu_each(toy_map):
    """Where markers overlap, each station gets its own submenu named after it."""
    menu = toy_map.build_station_menu(["B", "C"])
    assert [a.text() for a in menu.actions()] == ["Station B", "Station C"]
    seen = []
    toy_map.station_action.connect(lambda action, sid: seen.append((action, sid)))
    menu.actions()[1].menu().actions()[2].trigger()
    assert seen == [("to", "C")]


# ---- main window -----------------------------------------------------------------------


def make_window(qtbot):
    """A shown main window on toy_metro."""
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()  # shortcuts only fire in the active window
    qtbot.waitUntil(window.isActiveWindow, timeout=2000)
    return window


def test_menu_actions_fill_the_fields_and_open_the_card(qtbot):
    """Set as From / To act like a search choice; details opens the card."""
    window = make_window(qtbot)
    window.on_station_action("from", "A")
    window.on_station_action("to", "D")
    assert (window.state.source, window.state.destination) == ("A", "D")
    assert window.from_box.field.text() == "Station A"
    window.on_station_action("details", "C")
    assert window.station_dialog.isVisible() and window.station_dialog.station_id == "C"


def test_the_card_buttons_fill_the_fields(qtbot):
    """Opening the card of C and pressing Set as To chooses C as the destination."""
    window = make_window(qtbot)
    window.show_station("C")
    window.station_dialog.to_button.click()
    assert window.state.destination == "C" and window.to_box.field.text() == "Station C"


def test_ctrl_i_opens_the_card_of_the_destination_else_the_source(qtbot):
    """Keyboard route to the card: To first, then From."""
    window = make_window(qtbot)
    qtbot.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    assert window.station_dialog is None
    assert "Choose a station first" in window.statusBar().currentMessage()
    window.choose("source", "A")
    qtbot.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    assert window.station_dialog.station_id == "A"
    window.station_dialog.close()
    window.choose("destination", "F")
    qtbot.keyClick(window, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    assert window.station_dialog.station_id == "F"
