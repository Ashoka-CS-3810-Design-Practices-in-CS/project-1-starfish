"""Route panel: expandable station lists per leg (FR7, [D53])."""

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import Qt

from metro.data import load_network
from metro.describe import between_names
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.route_panel import TOGGLE_ROLE, RoutePanel


@pytest.fixture(scope="module")
def toy():
    """toy_metro with its graph."""
    network = load_network(TOY_METRO)
    return network, build_graph(network)


@pytest.fixture(scope="module")
def real():
    """The real network with its graph."""
    network = load_network(REAL_DATA)
    return network, build_graph(network)


def make_panel(qtbot, network, route):
    """A panel showing a route."""
    panel = RoutePanel(network)
    qtbot.addWidget(panel)
    panel.show_route(route)
    return panel


def texts(panel):
    """The text of every row."""
    return [panel.rows.item(i).text() for i in range(panel.rows.count())]


def toggle_row(panel, nth=0):
    """The nth 'stations in between' item."""
    items = [panel.rows.item(i) for i in range(panel.rows.count())]
    return [it for it in items if it.data(TOGGLE_ROLE) is not None][nth]


def test_a_leg_with_stations_in_between_gets_a_closed_toggle_row(qtbot, toy):
    """TM2: the Red leg passes B, so it has '▶ 1 station in between'; the Blue leg has none."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    assert texts(panel)[1] == "▶ 1 station in between"
    assert sum(t.startswith(("▶", "▼")) for t in texts(panel)) == 1


def test_clicking_the_toggle_lists_the_stations_in_order(qtbot, real):
    """Rajiv Chowk -> Hauz Khas: opening shows the 8 stations passed, in travel order."""
    network, graph = real
    by_name = {s.name: i for i, s in network.stations.items()}
    route = find_route(graph, network, by_name["Rajiv Chowk"], by_name["Hauz Khas"])
    panel = make_panel(qtbot, network, route)
    panel.on_item_clicked(toggle_row(panel))
    rows = texts(panel)
    assert rows[1] == "▼ 8 stations in between"
    assert [r.strip(" ·") for r in rows[2:]] == between_names(network, route.legs[0])
    assert len(rows) == 2 + 8


def test_clicking_the_toggle_again_closes_it(qtbot, toy):
    """A second click returns the panel to its first state."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    before = texts(panel)
    panel.on_item_clicked(toggle_row(panel))
    assert texts(panel) != before and "· Station B" in " ".join(texts(panel))
    panel.on_item_clicked(toggle_row(panel))
    assert texts(panel) == before


def test_each_leg_opens_independently(qtbot, real):
    """With two long legs, opening one leaves the other closed."""
    network, graph = real
    by_name = {s.name: i for i, s in network.stations.items()}
    route = find_route(graph, network, by_name["Samaypur Badli"], by_name["Noida City Centre"])
    panel = make_panel(qtbot, network, route)
    panel.on_item_clicked(toggle_row(panel, 0))
    rows = texts(panel)
    assert sum(r.startswith("▼") for r in rows) == 1 and sum(r.startswith("▶") for r in rows) == 1


def test_clicking_a_toggle_does_not_focus_the_map_but_a_leg_does(qtbot, toy):
    """leg_clicked fires for leg rows only."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    clicked = []
    panel.leg_clicked.connect(clicked.append)
    panel.on_item_clicked(toggle_row(panel))
    assert clicked == []
    panel.on_item_clicked(panel.rows.item(0))
    assert len(clicked) == 1 and clicked[0].line_id == "RED"


def test_clicking_a_station_row_does_nothing(qtbot, toy):
    """The open list is plain text: no focus change, no collapse."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    panel.on_item_clicked(toggle_row(panel))
    clicked = []
    panel.leg_clicked.connect(clicked.append)
    before = texts(panel)
    panel.on_item_clicked(panel.rows.item(2))  # '· Station B'
    assert clicked == [] and texts(panel) == before


def test_enter_and_space_toggle_the_current_row(qtbot, toy):
    """Keyboard users open a list with Enter or Space ([D20])."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    panel.show()
    panel.rows.setFocus()
    panel.rows.setCurrentRow(1)
    qtbot.keyClick(panel.rows, Qt.Key.Key_Return)
    assert texts(panel)[1].startswith("▼")
    assert panel.rows.currentRow() == 1
    qtbot.keyClick(panel.rows, Qt.Key.Key_Space)
    assert texts(panel)[1].startswith("▶")


def test_enter_on_a_leg_row_focuses_the_leg(qtbot, toy):
    """Enter still works on leg rows as before."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    panel.show()
    panel.rows.setFocus()
    panel.rows.setCurrentRow(0)
    with qtbot.waitSignal(panel.leg_clicked):
        qtbot.keyClick(panel.rows, Qt.Key.Key_Return)


def test_a_new_route_closes_every_list(qtbot, toy):
    """Opening a list, then showing another route, starts closed."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    panel.on_item_clicked(toggle_row(panel))
    panel.show_route(find_route(graph, network, "A", "F", "fewest_stops"))
    assert panel.expanded == set()
    assert not any(t.startswith("▼") for t in texts(panel))


def test_clearing_the_route_empties_the_panel(qtbot, toy):
    """show_route(None) leaves no rows and no summary."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    panel.show_route(None)
    assert panel.rows.count() == 0 and panel.summary.text() == ""


def test_toggle_rows_have_a_spoken_description(qtbot, toy):
    """Screen readers get 'Show 1 station in between', not the arrow glyph ([D20])."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "F"))
    item = toggle_row(panel)
    assert item.data(Qt.ItemDataRole.AccessibleTextRole) == "Show 1 station in between"
    panel.on_item_clicked(item)
    assert toggle_row(panel).data(Qt.ItemDataRole.AccessibleTextRole) == \
        "Hide 1 station in between"


def test_a_walk_leg_has_no_toggle(qtbot, toy):
    """TM10 A -> H ends with a WALK leg of two stations: nothing in between to list."""
    network, graph = toy
    panel = make_panel(qtbot, network, find_route(graph, network, "A", "H"))
    walk_rows = [t for t in texts(panel) if t.startswith("2. Walk")]
    assert len(walk_rows) == 1
    assert sum(t.startswith(("▶", "▼")) for t in texts(panel)) == 1  # only the Red leg's
