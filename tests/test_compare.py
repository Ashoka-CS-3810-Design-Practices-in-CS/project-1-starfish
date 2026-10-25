"""Alternative-route tabs and the comparison dialog (FR17, [D56])."""

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import Qt

from metro.alternatives import find_alternative_routes
from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.compare_dialog import ROW_BEST, ROW_LINES, RouteCompareDialog
from metro.ui.main_window import MainWindow
from metro.ui.route_panel import RoutePanel

TOY = load_network(TOY_METRO)
TOY_GRAPH = build_graph(TOY)
TM2, TM6 = find_alternative_routes(TOY_GRAPH, TOY, "A", "F")[:2]  # fastest, fewest stops


def cell(dialog, row, column):
    """Text of a table cell."""
    return dialog.table.item(row, column).text()


# ---- the tabs in the panel -------------------------------------------------------------------


def test_tabs_and_compare_button_are_hidden_without_alternatives(qtbot):
    """One route (or none) leaves nothing to choose between."""
    panel = RoutePanel(TOY)
    qtbot.addWidget(panel)
    panel.show()
    for routes in ((), (TM2,)):
        panel.show_alternatives(routes, 0)
        assert not panel.tabs.isVisible() and not panel.compare_button.isVisible()
        assert not panel.caption.isVisible()


def test_tabs_are_numbered_and_the_caption_says_what_the_selected_route_wins(qtbot):
    """Tabs are plain 'Route N' so they always fit; the caption and tooltips carry the rest."""
    panel = RoutePanel(TOY)
    qtbot.addWidget(panel)
    panel.show()
    panel.show_alternatives((TM2, TM6), 0)
    assert [panel.tabs.tabText(i) for i in range(2)] == ["Route 1", "Route 2"]
    assert panel.tabs.tabToolTip(1) == \
        "Estimated 13 min · 1 interchange · 2 stops - Fewest interchanges, Fewest stops"
    assert panel.caption.text() == "Best at: Fastest, Fewest interchanges"
    panel.tabs.setCurrentIndex(1)
    assert panel.caption.text() == "Best at: Fewest interchanges, Fewest stops"
    assert panel.tabs.isVisible() and panel.caption.isVisible()
    assert panel.compare_button.isVisible()


def test_setting_the_tab_from_code_does_not_announce_a_choice(qtbot):
    """Syncing the tabs with the state must not loop back as a user choice."""
    panel = RoutePanel(TOY)
    qtbot.addWidget(panel)
    chosen = []
    panel.alternative_chosen.connect(chosen.append)
    panel.show_alternatives((TM2, TM6), 1)
    assert chosen == [] and panel.tabs.currentIndex() == 1
    panel.tabs.setCurrentIndex(0)  # what a click does
    assert chosen == [0]


def test_compare_button_asks_for_the_comparison(qtbot):
    """The panel only asks; the window decides what to open."""
    panel = RoutePanel(TOY)
    qtbot.addWidget(panel)
    panel.show()
    panel.show_alternatives((TM2, TM6), 0)
    with qtbot.waitSignal(panel.compare_requested):
        qtbot.mouseClick(panel.compare_button, Qt.MouseButton.LeftButton)


# ---- the dialog ------------------------------------------------------------------------------


def make_dialog(qtbot, routes=(TM2, TM6), selected=0):
    """A comparison dialog on toy_metro."""
    dialog = RouteCompareDialog(TOY, routes, selected)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_dialog_shows_one_column_per_route_with_its_measures(qtbot):
    """TM2: 12 min, 1 interchange, 3 stops, Red then Blue; TM6: 13 min, 1, 2, Red then Green."""
    dialog = make_dialog(qtbot)
    assert dialog.table.columnCount() == 2
    assert [cell(dialog, r, 0) for r in range(3)] == ["12 min", "1", "3"]
    assert [cell(dialog, r, 1) for r in range(3)] == ["13 min", "1", "2"]
    assert cell(dialog, ROW_LINES, 0) == "Red Line, Blue Line"
    assert cell(dialog, ROW_LINES, 1) == "Red Line, Green Line"
    assert cell(dialog, ROW_BEST, 0) == "Fastest; Fewest interchanges"
    assert cell(dialog, ROW_BEST, 1) == "Fewest interchanges; Fewest stops"


def bold(dialog, row, column):
    """Whether a cell is bold."""
    return dialog.table.item(row, column).font().bold()


def test_the_best_value_in_each_row_is_bold_and_ties_are_both_bold(qtbot):
    """Fastest is TM2; both tie on interchanges; stops is TM6."""
    dialog = make_dialog(qtbot)
    assert [bold(dialog, 0, c) for c in (0, 1)] == [True, False]
    assert [bold(dialog, 1, c) for c in (0, 1)] == [True, True]
    assert [bold(dialog, 2, c) for c in (0, 1)] == [False, True]


def test_the_route_on_screen_says_showing_now_and_cannot_be_chosen(qtbot):
    """Its button is disabled; the other offers 'Choose this route'."""
    dialog = make_dialog(qtbot, selected=1)
    assert [b.text() for b in dialog.buttons] == ["Choose this route", "Showing now"]
    assert [b.isEnabled() for b in dialog.buttons] == [True, False]
    assert [b.accessibleName() for b in dialog.buttons] == ["Choose route 1", "Choose route 2"]


def test_choosing_a_route_emits_its_index_and_closes(qtbot):
    """The second route's button sends 1."""
    dialog = make_dialog(qtbot)
    with qtbot.waitSignal(dialog.route_chosen) as blocker:
        dialog.buttons[1].click()
    assert blocker.args == [1] and not dialog.isVisible()


def test_a_walk_only_route_says_so(qtbot):
    """D -> H is a single walk: no line is ridden."""
    walk = find_route(TOY_GRAPH, TOY, "D", "H")
    assert [leg.kind for leg in walk.legs] == ["WALK"]
    dialog = make_dialog(qtbot, routes=(walk, TM2))
    assert cell(dialog, ROW_LINES, 0) == "Walk only"


def test_the_title_names_the_journey(qtbot):
    """So several open windows can be told apart."""
    assert make_dialog(qtbot).windowTitle() == "Compare routes: Station A → Station F"


# ---- in the window -------------------------------------------------------------------------


def make_window(qtbot, folder=None):
    """A shown main window on toy_metro or another dataset."""
    network = load_network(folder) if folder else TOY
    window = MainWindow(network, build_graph(network))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    return window


def shown_a_to_f(qtbot):
    """A window with the A -> F route on screen."""
    window = make_window(qtbot)
    window.on_map_click("A")
    window.on_map_click("F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    return window


def test_a_search_fills_the_tabs(qtbot):
    """A -> F has at least the fastest and the fewest-stops route, fastest selected."""
    window = shown_a_to_f(qtbot)
    tabs = window.route_panel.tabs
    assert tabs.isVisible() and tabs.count() == len(window.state.alternatives) >= 2
    assert tabs.currentIndex() == window.state.selected == 0


def test_clicking_a_tab_shows_that_route_everywhere(qtbot):
    """Panel summary, rows and the map all follow the chosen route."""
    window = shown_a_to_f(qtbot)
    window.route_panel.tabs.setCurrentIndex(1)
    other = window.state.alternatives[1]
    assert window.state.route == other and window.state.selected == 1
    assert window.route_panel.summary.text().startswith(f"Estimated {13} min")
    assert len(window.map.overlay.dots) == len({s for leg in other.legs for s in leg.stations})
    assert window.map.route == other


def test_going_back_to_the_first_tab_restores_the_first_route(qtbot):
    """Switching is reversible and keeps the list."""
    window = shown_a_to_f(qtbot)
    first = window.state.route
    window.route_panel.tabs.setCurrentIndex(1)
    window.route_panel.tabs.setCurrentIndex(0)
    assert window.state.route == first and len(window.state.alternatives) >= 2


def test_compare_button_opens_the_dialog_and_choosing_shows_that_route(qtbot):
    """From the comparison, 'Choose this route' on column 2 shows that route and its tab."""
    window = shown_a_to_f(qtbot)
    qtbot.mouseClick(window.route_panel.compare_button, Qt.MouseButton.LeftButton)
    dialog = window.compare_dialog
    assert dialog.isVisible() and dialog.table.columnCount() == len(window.state.alternatives)
    dialog.buttons[1].click()
    assert window.state.selected == 1 and window.route_panel.tabs.currentIndex() == 1
    assert not dialog.isVisible()


def test_no_comparison_with_a_single_route(qtbot):
    """A route with no alternatives gives no dialog even if asked."""
    window = make_window(qtbot)
    window.on_map_click("A")
    window.on_map_click("C")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert len(window.state.alternatives) == 1
    window.show_comparison()
    assert window.compare_dialog is None
    assert not window.route_panel.tabs.isVisible()


def test_a_new_search_or_reset_hides_the_tabs(qtbot):
    """The alternatives belong to the stations they were found for."""
    window = shown_a_to_f(qtbot)
    window.reset()
    assert window.state.alternatives == () and not window.route_panel.tabs.isVisible()
    assert window.route_panel.tabs.count() == 0


def test_changing_the_criterion_reselects_the_first_tab(qtbot):
    """Fewest stops makes the TM6 route the first alternative."""
    window = shown_a_to_f(qtbot)
    window.criterion.setCurrentIndex(2)
    qtbot.waitUntil(lambda: window.state.route is not None and window.state.route.stops == 2)
    assert window.state.selected == 0 and window.route_panel.tabs.currentIndex() == 0
    assert "Fewest stops" in window.route_panel.caption.text()


def test_real_data_journey_has_labelled_tabs(qtbot):
    """Samaypur Badli -> Noida City Centre gets three tabs, the first being the fastest."""
    window = make_window(qtbot, REAL_DATA)
    by_name = {s.name: i for i, s in window.network.stations.items()}
    window.on_map_click(by_name["Samaypur Badli"])
    window.on_map_click(by_name["Noida City Centre"])
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    tabs = window.route_panel.tabs
    assert tabs.count() == 3 and tabs.tabText(2) == "Route 3"
    assert window.route_panel.caption.text().startswith("Best at: Fastest")
    window.route_panel.tabs.setCurrentIndex(1)
    assert window.route_panel.caption.text() == "Best at: Fewest stops"
    window.route_panel.tabs.setCurrentIndex(2)  # a longer way round that wins nothing
    assert window.route_panel.caption.text() == "Best at: -"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_dialog_opens_in_either_theme(qtbot, theme):
    """The comparison inherits the window's style sheet without errors."""
    window = shown_a_to_f(qtbot)
    if theme == "dark":
        window.toggle_theme()
    window.show_comparison()
    assert window.compare_dialog.isVisible()
