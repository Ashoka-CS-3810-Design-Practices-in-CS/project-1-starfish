"""Exporting the route on screen: clipboard, text file, Markdown file (Could tier, [D57])."""

import pytest
from conftest import TOY_METRO
from PySide6.QtWidgets import QApplication

from metro.data import load_network
from metro.describe import export_route_text
from metro.graph import build_graph
from metro.router import find_route
from metro.ui.export import default_filename, ensure_suffix, export_route, write_export
from metro.ui.main_window import MainWindow
from metro.ui.route_panel import RoutePanel

TOY = load_network(TOY_METRO)
ROUTE = find_route(build_graph(TOY), TOY, "A", "F")


# ---- pure helpers -------------------------------------------------------------------------


@pytest.mark.parametrize("title, expected", [
    ("Rajiv Chowk → Hauz Khas", "Rajiv-Chowk-to-Hauz-Khas.txt"),
    ("Dilli Haat - INA → Kashmere Gate", "Dilli-Haat-INA-to-Kashmere-Gate.txt"),
    ('Bad: name/with\\chars?*<>|"', "Bad-name-with-chars.txt"),
    ("", "route.txt"),
    ("→", "to.txt"),
])
def test_default_filename_is_safe_on_windows(title, expected):
    """No character that Windows forbids, no spaces, never empty."""
    assert default_filename(title, "txt") == expected


def test_default_filename_uses_the_format_as_extension():
    """Markdown gets .md."""
    assert default_filename("A → B", "md") == "A-to-B.md"


def test_ensure_suffix_only_adds_a_missing_extension():
    """A typed extension is respected, even an unusual one."""
    assert ensure_suffix("/tmp/route", "md") == "/tmp/route.md"
    assert ensure_suffix("/tmp/route.text", "md") == "/tmp/route.text"


def test_write_export_writes_utf8(tmp_path):
    """The arrows and dots survive a round trip through the file. The bytes are checked as
    UTF-8 text with line ends normalised, because Windows writes \\r\\n."""
    path = tmp_path / "r.txt"
    assert write_export(str(path), "A → B · ⇒\n") is None
    assert path.read_bytes().decode("utf-8").replace("\r\n", "\n") == "A → B · ⇒\n"


def test_write_export_reports_a_problem_instead_of_raising(tmp_path):
    """ER16: a missing folder or a folder-as-file gives a message naming the path."""
    for bad in (tmp_path / "no" / "such" / "dir" / "r.txt", tmp_path):
        message = write_export(str(bad), "x")
        assert message.startswith(f"Could not save the route to {bad}:")
        assert message.endswith(".")


# ---- export_route -----------------------------------------------------------------------


def patch_dialog(monkeypatch, result):
    """Replace the file dialog with one that returns `result` and records its arguments."""
    seen = {}

    def fake(parent, caption, directory, filter_):
        seen.update(caption=caption, directory=directory, filter=filter_)
        return result, filter_
    monkeypatch.setattr("metro.ui.export.QFileDialog.getSaveFileName", fake)
    return seen


def test_copy_puts_the_text_on_the_clipboard(qtbot):
    """The clipboard gets exactly the text export."""
    assert export_route(None, TOY, ROUTE, "copy") == ("info", "Route copied to the clipboard.")
    assert QApplication.clipboard().text() == export_route_text(TOY, ROUTE, "txt")


@pytest.mark.parametrize("kind, format", [("txt", "txt"), ("md", "md")])
def test_save_writes_the_chosen_format(qtbot, tmp_path, monkeypatch, kind, format):
    """Text and Markdown files hold what export_route_text gives, and the dialog is offered a
    sensible name and filter."""
    target = tmp_path / f"out.{format}"
    seen = patch_dialog(monkeypatch, str(target))
    level, message = export_route(None, TOY, ROUTE, kind)
    assert (level, message) == ("info", f"Saved to {target}")
    assert target.read_text(encoding="utf-8") == export_route_text(TOY, ROUTE, format)
    assert seen["directory"] == f"Station-A-to-Station-F.{format}"
    assert format in seen["filter"]


def test_a_name_without_extension_gets_one(qtbot, tmp_path, monkeypatch):
    """Typing 'myroute' saves 'myroute.md'."""
    patch_dialog(monkeypatch, str(tmp_path / "myroute"))
    export_route(None, TOY, ROUTE, "md")
    assert (tmp_path / "myroute.md").exists()


def test_cancelling_the_dialog_saves_nothing_and_says_nothing(qtbot, tmp_path, monkeypatch):
    """An empty path means cancel."""
    patch_dialog(monkeypatch, "")
    assert export_route(None, TOY, ROUTE, "txt") is None
    assert list(tmp_path.iterdir()) == []


def test_a_failed_save_comes_back_as_an_error(qtbot, tmp_path, monkeypatch):
    """Saving into a folder that does not exist gives ('error', message)."""
    patch_dialog(monkeypatch, str(tmp_path / "missing" / "r.txt"))
    level, message = export_route(None, TOY, ROUTE, "txt")
    assert level == "error" and message.startswith("Could not save the route")


# ---- panel and window ---------------------------------------------------------------------


def test_export_button_appears_with_a_route_and_offers_three_actions(qtbot):
    """Hidden when empty; Copy, Save as text, Save as Markdown when a route is shown."""
    panel = RoutePanel(TOY)
    qtbot.addWidget(panel)
    panel.show()
    assert not panel.export_button.isVisible()
    panel.show_route(ROUTE)
    assert panel.export_button.isVisible()
    assert panel.export_button.accessibleName() == "Export route"
    actions = panel.export_button.menu().actions()
    assert [a.text() for a in actions] == ["Copy to clipboard", "Save as text…",
                                           "Save as Markdown…"]
    sent = []
    panel.export_requested.connect(sent.append)
    for action in actions:
        action.trigger()
    assert sent == ["copy", "txt", "md"]
    panel.show_route(None)
    assert not panel.export_button.isVisible()


def shown_window(qtbot):
    """A window with the A -> F route on screen."""
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.waitExposed(window)
    window.on_map_click("A")
    window.on_map_click("F")
    qtbot.waitUntil(lambda: window.state.phase == "RouteShown")
    return window


def test_window_copy_reports_in_the_status_bar(qtbot):
    """Copying shows a short confirmation and leaves the banner alone."""
    window = shown_window(qtbot)
    window.on_export("copy")
    assert window.statusBar().currentMessage() == "Route copied to the clipboard."
    assert window.state.message is None
    assert QApplication.clipboard().text().startswith("Station A → Station F")


def test_window_save_failure_goes_to_the_banner_and_keeps_the_route(qtbot, tmp_path, monkeypatch):
    """ER16: the error is visible in the banner; the route and selection are untouched."""
    patch_dialog(monkeypatch, str(tmp_path / "missing" / "dir" / "r.txt"))
    window = shown_window(qtbot)
    route = window.state.route
    window.on_export("txt")
    assert window.banner.isVisible()
    assert window.state.message.startswith("Could not save the route")
    assert window.state.message_kind == "error"
    assert window.state.route == route and window.state.source == "A"


def test_window_save_success_goes_to_the_status_bar(qtbot, tmp_path, monkeypatch):
    """The file exists and the user is told where."""
    target = tmp_path / "trip.md"
    patch_dialog(monkeypatch, str(target))
    window = shown_window(qtbot)
    window.on_export("md")
    assert target.read_text(encoding="utf-8").startswith("# Station A → Station F")
    assert window.statusBar().currentMessage() == f"Saved to {target}"


def test_export_with_no_route_does_nothing(qtbot, monkeypatch):
    """A stale menu click cannot export an empty route."""
    patch_dialog(monkeypatch, "should-not-be-used")
    window = MainWindow(TOY, build_graph(TOY))
    qtbot.addWidget(window)
    window.on_export("txt")
    assert window.state.message is None
