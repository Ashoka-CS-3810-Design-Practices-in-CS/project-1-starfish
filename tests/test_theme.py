"""Light and dark themes: palette, map recolouring, the toggle and persistence ([D55])."""

import re
from pathlib import Path

import pytest
from conftest import REAL_DATA, TOY_METRO
from PySide6.QtCore import Qt

from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.app_settings import app_settings
from metro.ui.main_window import MainWindow
from metro.ui.map_view import MapView
from metro.ui.route_panel import Banner
from metro.ui.theme import DARK, LIGHT, contrast_ratio, other_theme, theme_named

TOY = load_network(TOY_METRO)
GLOW_Z = 4.5


# ---- settings isolation (protects the developer's real preferences) ----------------------


def test_settings_for_tests_live_in_the_temporary_folder(tmp_path):
    """The autouse fixture redirects QSettings; nothing here may touch real preferences."""
    settings = app_settings()
    settings.setValue("probe", 1)
    settings.sync()
    saved = Path(settings.fileName()).resolve()  # Qt gives forward slashes, even on Windows
    assert saved.is_relative_to(tmp_path.resolve()) and saved.suffix == ".ini"


# ---- pure theme data -----------------------------------------------------------------------


def test_theme_named_falls_back_to_light():
    """Unknown or damaged saved values never crash and never give a half-theme."""
    assert theme_named("dark") is DARK and theme_named("light") is LIGHT
    for bad in (None, 3, "solarized", "", b"dark", ["dark"]):
        assert theme_named(bad) is LIGHT


def test_other_theme_switches_both_ways():
    """The toggle alternates."""
    assert other_theme(LIGHT) is DARK and other_theme(DARK) is LIGHT


def rgb(colour: str) -> str:
    """'#AARRGGBB' or '#RRGGBB' as '#RRGGBB'."""
    return "#" + colour[-6:]


@pytest.mark.parametrize("theme", [LIGHT, DARK], ids=lambda t: t.name)
def test_map_text_has_enough_contrast(theme):
    """Station names and badge text reach WCAG AA (4.5:1) on their backgrounds."""
    assert contrast_ratio(theme.label, theme.background) >= 4.5
    assert contrast_ratio(theme.badge_text, rgb(theme.badge_fill)) >= 4.5


@pytest.mark.parametrize("theme, window_bg", [(LIGHT, "#FFFFFF"), (DARK, "#202124")],
                         ids=["light", "dark"])
def test_hint_and_banner_text_have_enough_contrast(theme, window_bg):
    """The red hint and both banner kinds are readable in each theme."""
    hint = re.search(r"QLabel#hint \{ color: (#\w{6});", theme.stylesheet).group(1)
    assert contrast_ratio(hint, window_bg) >= 4.5
    for kind in ("error", "info"):
        block = re.search(rf'#banner\[kind="{kind}"\] \{{ background: (#\w{{6}});',
                          theme.stylesheet).group(1)
        text = re.search(rf'#banner\[kind="{kind}"\] QLabel \{{[^}}]*color: (#\w{{6}});',
                         theme.stylesheet).group(1)
        assert contrast_ratio(text, block) >= 4.5, (theme.name, kind)


def test_dark_theme_restyles_widgets_and_light_leaves_them_native():
    """Only the dark sheet repaints every widget; the light one has no blanket rule."""
    assert "QWidget {" in DARK.stylesheet and "QWidget {" not in LIGHT.stylesheet


# ---- map ------------------------------------------------------------------------------------


@pytest.fixture
def toy_map(qtbot):
    """A shown map of toy_metro with a route available."""
    view = MapView(TOY)
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    qtbot.waitExposed(view)
    view.fit_all()
    view.route_a_to_f = find_route(build_graph(TOY), TOY, "A", "F")
    return view


def test_dark_map_uses_the_dark_background_labels_and_markers(toy_map):
    """set_theme(DARK) recolours background, label text and station dots."""
    toy_map.set_theme(DARK)
    assert toy_map.backgroundBrush().color().name().upper() == "#18191D"
    assert toy_map.labels["C"].brush().color().name().upper() == DARK.label
    assert toy_map.markers["C"].brush().color().name().upper() == DARK.interchange_fill  # hub
    assert toy_map.markers["A"].brush().color().name().upper() == DARK.marker_fill
    toy_map.set_theme(LIGHT)
    assert toy_map.backgroundBrush().color().name().upper() == "#FAFAF7"
    assert toy_map.markers["A"].brush().color().name().upper() == LIGHT.marker_fill


def test_a_closed_station_stays_grey_in_both_themes(qtbot):
    """Closed stations keep their closed fill and half opacity when the theme changes."""
    from conftest import close_stations
    view = MapView(close_stations(TOY, "B"))
    qtbot.addWidget(view)
    for theme in (DARK, LIGHT):
        view.set_theme(theme)
        assert view.markers["B"].brush().color().name().upper() == theme.closed_fill
        assert view.markers["B"].opacity() == pytest.approx(0.5)


def test_dark_route_gets_a_glow_and_light_does_not(toy_map):
    """The halo items (z 4.5) exist only in the dark theme, and follow the theme live."""
    toy_map.show_route(toy_map.route_a_to_f)

    def halos():
        return [i for i in toy_map.overlay.items if i.zValue() == GLOW_Z]
    assert halos() == []
    toy_map.set_theme(DARK)
    assert len(halos()) >= 2
    toy_map.set_theme(LIGHT)
    assert halos() == []


def test_switching_theme_keeps_the_view_the_route_and_the_dimming(toy_map):
    """The theme change must not move the camera, lose dots or un-dim the network."""
    toy_map.show_route(toy_map.route_a_to_f)
    transform, zoom = toy_map.transform(), toy_map.zoom()
    dots, badges = len(toy_map.overlay.dots), len(toy_map.overlay.badges)
    toy_map.set_theme(DARK)
    assert toy_map.transform() == transform and toy_map.zoom() == pytest.approx(zoom)
    assert (len(toy_map.overlay.dots), len(toy_map.overlay.badges)) == (dots, badges)
    assert toy_map.markers["E"].opacity() == pytest.approx(0.25)  # off the route
    assert toy_map.markers["A"].opacity() == pytest.approx(1.0)  # on the route
    assert toy_map.overlay.badges[0].brush().color().name().upper() == DARK.badge_text


def test_theme_button_describes_what_it_switches_to(toy_map):
    """The accessible name and tooltip say where a click leads."""
    button = toy_map.controls.theme_button
    assert button.accessibleName() == "Switch to dark theme"
    toy_map.set_theme(DARK)
    assert button.accessibleName() == "Switch to light theme"
    assert button.toolTip() == "Switch to the light theme"


# ---- banner -----------------------------------------------------------------------------


def test_banner_kind_is_a_property_so_the_style_sheet_can_colour_it(qtbot):
    """The banner no longer carries colours itself."""
    banner = Banner()
    qtbot.addWidget(banner)
    banner.show_message("Something", "error", None)
    assert banner.property("kind") == "error" and banner.styleSheet() == ""
    banner.show_message("Else", "info", "Reset")
    assert banner.property("kind") == "info"


# ---- window -----------------------------------------------------------------------------


def make_window(qtbot):
    """A shown main window on toy_metro using the (redirected) app settings."""
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    return window


def test_window_starts_light_by_default(qtbot):
    """No saved choice means the light theme."""
    window = make_window(qtbot)
    assert window.theme is LIGHT and window.map.theme is LIGHT
    assert window.styleSheet() == LIGHT.stylesheet


def test_the_theme_button_toggles_the_whole_window(qtbot):
    """Clicking the map's theme button restyles window and map; clicking again undoes it."""
    window = make_window(qtbot)
    qtbot.mouseClick(window.map.controls.theme_button, Qt.MouseButton.LeftButton)
    assert window.theme is DARK and window.map.theme is DARK
    assert window.styleSheet() == DARK.stylesheet
    qtbot.mouseClick(window.map.controls.theme_button, Qt.MouseButton.LeftButton)
    assert window.theme is LIGHT and window.styleSheet() == LIGHT.stylesheet


def test_the_choice_is_remembered_by_the_next_window(qtbot):
    """Dark is saved; a new window starts dark."""
    window = make_window(qtbot)
    window.toggle_theme()
    assert app_settings().value("theme") == "dark"
    assert make_window(qtbot).theme is DARK


def test_a_damaged_saved_theme_gives_light(qtbot):
    """A hand-edited or old settings file cannot break start-up."""
    app_settings().setValue("theme", "neon")
    assert make_window(qtbot).theme is LIGHT


def test_toggling_with_a_route_on_screen_keeps_it(qtbot):
    """The route, its panel rows and the state survive a theme change."""
    window = make_window(qtbot)
    window.on_map_click("A")
    window.on_map_click("F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    rows = window.route_panel.rows.count()
    dots = len(window.map.overlay.dots)
    window.toggle_theme()
    assert window.state.phase == "RouteShown"
    assert window.route_panel.rows.count() == rows and len(window.map.overlay.dots) == dots


def test_dark_window_works_on_real_data(qtbot):
    """Smoke test: the dark theme builds and shows a long route without errors."""
    network = load_network(REAL_DATA)
    window = MainWindow(network, build_graph(network))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    window.toggle_theme()
    by_name = {s.name: i for i, s in network.stations.items()}
    window.on_map_click(by_name["Samaypur Badli"])
    window.on_map_click(by_name["Noida City Centre"])
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    assert window.map.overlay.badges
