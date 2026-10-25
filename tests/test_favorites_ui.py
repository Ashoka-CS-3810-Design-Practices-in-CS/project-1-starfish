"""Favourites bar and its use in the main window (Could tier, [D48])."""

import json

import pytest
from conftest import TOY_METRO, close_stations
from PySide6.QtCore import Qt

from metro.data import load_network
from metro.favorites import Favorite
from metro.graph import build_graph
from metro.ui.app_settings import app_settings
from metro.ui.favorites_bar import SETTINGS_KEY, FavoritesBar
from metro.ui.main_window import MainWindow

TOY = load_network(TOY_METRO)
A_TO_F = Favorite("A", "F", "fastest")
B_TO_E = Favorite("B", "E", "fewest_stops")


def make_bar(qtbot, network=TOY):
    """A bar using the (redirected) app settings."""
    bar = FavoritesBar(network, app_settings())
    qtbot.addWidget(bar)
    bar.show()
    return bar


def menu_texts(bar):
    """Text of the top-level menu entries."""
    return [a.text() for a in bar.menu.actions()]


def stored(bar):
    """The list as saved in settings."""
    return json.loads(bar.settings.value(SETTINGS_KEY))


# ---- the bar alone -----------------------------------------------------------------------------


def test_star_is_off_until_a_route_is_on_screen(qtbot):
    """Nothing to save yet: disabled, with a reason."""
    bar = make_bar(qtbot)
    assert not bar.star.isEnabled() and bar.star.toolTip() == "Find a route first."
    assert menu_texts(bar) == ["No favourites yet"] and not bar.menu.actions()[0].isEnabled()


def test_clicking_the_star_saves_the_route_and_lists_it(qtbot):
    """Saved to settings, shown in the menu with names and criterion, star turns solid."""
    bar = make_bar(qtbot)
    bar.set_journey(A_TO_F)
    assert bar.star.text() == "☆ Add to favourites"
    qtbot.mouseClick(bar.star, Qt.MouseButton.LeftButton)
    assert stored(bar) == [{"from": "A", "to": "F", "criterion": "fastest"}]
    assert menu_texts(bar)[0] == "Station A → Station F · Fastest"
    assert bar.star.text() == "★ Saved - click to remove"
    assert bar.star.accessibleName() == "Remove from favourites"


def test_clicking_a_solid_star_removes_the_favourite(qtbot):
    """A second click undoes the first."""
    bar = make_bar(qtbot)
    bar.set_journey(A_TO_F)
    bar.star.click()
    bar.star.click()
    assert stored(bar) == [] and menu_texts(bar) == ["No favourites yet"]
    assert bar.star.accessibleName() == "Add to favourites"


def test_the_same_stations_with_another_criterion_are_a_different_favourite(qtbot):
    """The star is solid only for the exact journey."""
    bar = make_bar(qtbot)
    bar.set_journey(A_TO_F)
    bar.star.click()
    bar.set_journey(Favorite("A", "F", "fewest_stops"))
    assert bar.star.text() == "☆ Add to favourites"


def test_newest_favourite_comes_first(qtbot):
    """Menu order is newest first."""
    bar = make_bar(qtbot)
    for journey in (A_TO_F, B_TO_E):
        bar.set_journey(journey)
        bar.star.click()
    assert menu_texts(bar)[:2] == ["Station B → Station E · Fewest stops",
                                   "Station A → Station F · Fastest"]


def test_picking_a_menu_entry_emits_its_journey(qtbot):
    """The entry sends source, destination and criterion."""
    bar = make_bar(qtbot)
    bar.set_journey(B_TO_E)
    bar.star.click()
    with qtbot.waitSignal(bar.chosen) as blocker:
        bar.menu.actions()[0].trigger()
    assert blocker.args == ["B", "E", "fewest_stops"]


def test_remove_submenu_deletes_one_favourite_even_when_not_on_screen(qtbot):
    """Menu removal works without having to show the route first."""
    bar = make_bar(qtbot)
    for journey in (A_TO_F, B_TO_E):
        bar.set_journey(journey)
        bar.star.click()
    bar.set_journey(None)
    remove = next(a for a in bar.menu.actions() if a.text() == "Remove").menu()
    remove.actions()[0].trigger()  # newest: B -> E
    assert stored(bar) == [{"from": "A", "to": "F", "criterion": "fastest"}]


def test_saved_favourites_come_back_in_the_next_bar(qtbot):
    """Persistence: a new bar reads what the old one wrote."""
    bar = make_bar(qtbot)
    bar.set_journey(A_TO_F)
    bar.star.click()
    assert menu_texts(make_bar(qtbot))[0] == "Station A → Station F · Fastest"


@pytest.mark.parametrize("damaged", ["not json", "{}", "[1, 2]", '[{"from": "A"}]'])
def test_a_damaged_saved_list_is_ignored(qtbot, damaged):
    """ER15: start-up works and the list is empty."""
    app_settings().setValue(SETTINGS_KEY, damaged)
    assert menu_texts(make_bar(qtbot)) == ["No favourites yet"]


def test_favourites_of_stations_that_no_longer_exist_are_dropped(qtbot):
    """A dataset change cannot leave a dead menu entry."""
    app_settings().setValue(SETTINGS_KEY, json.dumps([
        {"from": "A", "to": "F"}, {"from": "A", "to": "GONE"}]))
    assert menu_texts(make_bar(qtbot))[0] == "Station A → Station F · Fastest"
    assert len([t for t in menu_texts(make_bar(qtbot)) if "→" in t]) == 1


def test_bar_controls_have_accessible_names(qtbot):
    """[D20] Star and menu button are named."""
    bar = make_bar(qtbot)
    assert bar.star.accessibleName() and bar.menu_button.accessibleName() == "Favourite routes"


# ---- in the window -----------------------------------------------------------------------------


def make_window(qtbot, network=TOY):
    """A shown main window using the redirected settings."""
    window = MainWindow(network, build_graph(network))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    return window


def shown(qtbot, window, src="A", dst="F"):
    """Choose two stations and wait for the route."""
    window.on_map_click(src)
    window.on_map_click(dst)
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")


def test_the_star_follows_the_route_on_screen(qtbot):
    """Off with no route, on once a route is shown, off again after Reset."""
    window = make_window(qtbot)
    assert not window.favorites.star.isEnabled()
    shown(qtbot, window)
    assert window.favorites.star.isEnabled() and window.favorites.journey == A_TO_F
    window.reset()
    assert not window.favorites.star.isEnabled()


def test_a_saved_route_is_recalled_in_a_new_window_with_its_criterion(qtbot):
    """Save B -> E (fewest stops); a fresh window picks it and shows that route."""
    window = make_window(qtbot)
    window.criterion.setCurrentIndex(2)
    shown(qtbot, window, "B", "E")
    window.favorites.star.click()
    second = make_window(qtbot)
    assert second.criterion.currentData() == "fastest"
    second.favorites.menu.actions()[0].trigger()
    qtbot.waitUntil(lambda: second.state.phase == "RouteShown")
    assert (second.state.source, second.state.destination) == ("B", "E")
    assert second.state.criterion == "fewest_stops"
    assert second.criterion.currentData() == "fewest_stops"
    assert second.from_box.field.text() == "Station B" and second.to_box.field.text() == "Station E"


def test_recalling_a_favourite_does_not_search_twice(qtbot):
    """Syncing the Criterion box must not trigger the criterion-change search."""
    window = make_window(qtbot)
    searches = []
    original = window.runner.start
    window.runner.start = lambda *args: (searches.append(args), original(*args))[1]
    window.on_favorite("B", "E", "fewest_stops")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert len(searches) == 1


def test_a_favourite_with_a_station_closed_since_gives_the_closed_message(qtbot):
    """ER6: the menu entry is still there; choosing it explains why nothing happens."""
    app_settings().setValue(SETTINGS_KEY, json.dumps([{"from": "A", "to": "F"}]))
    network = close_stations(TOY, "F")
    window = make_window(qtbot, network)
    window.favorites.menu.actions()[0].trigger()
    assert window.state.message == "Station Station F is closed and cannot be used."
    assert window.state.phase == "Idle" and window.state.route is None


def test_tab_order_reaches_the_favourites_controls(qtbot):
    """Keyboard users can reach the star and the menu between Reset and the route list."""
    window = make_window(qtbot)
    chain = window.panel.tab_chain()
    assert chain.index(window.reset_button) < chain.index(window.favorites.star) \
        < chain.index(window.favorites.menu_button) < chain.index(window.route_panel.rows)
