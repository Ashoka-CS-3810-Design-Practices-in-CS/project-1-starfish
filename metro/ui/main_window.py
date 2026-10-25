"""The main window: layout, wiring and keyboard shortcuts (FR4, FR13, FR14, [D20]).

All decisions about *what* to show live in `metro.app_state`. This file only turns user
actions into AppState updates and then redraws everything from the new state (`apply`).
"""

import logging

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from metro import app_state as st
from metro.alternatives import find_alternative_routes
from metro.favorites import Favorite
from metro.graph import RoutingGraph
from metro.models import Network
from metro.router import find_route
from metro.ui.app_settings import app_settings
from metro.ui.compare_dialog import RouteCompareDialog
from metro.ui.extras import ExtrasMixin
from metro.ui.map_view import MapView
from metro.ui.search_box import SearchBox
from metro.ui.side_panel import SidePanel
from metro.ui.station_dialog import StationDialog
from metro.ui.theme import theme_named
from metro.ui.worker import RouteRunner

log = logging.getLogger(__name__)

NARROW_PX = 1100  # below this width the side panel hides behind a toggle


class MainWindow(ExtrasMixin, QMainWindow):
    """Side panel (search, controls, route) on the left, map on the right."""

    def __init__(self, network: Network, graph: RoutingGraph, find=find_route,
                 watchdog_ms: int = 2000, settings: QSettings | None = None):
        """`find` and `watchdog_ms` only change in tests (a slow fake, a short watchdog)."""
        super().__init__()
        self.network = network
        self.graph = graph
        self.settings = settings or app_settings()
        self.theme = theme_named(self.settings.value("theme"))
        self.state = st.AppState()
        self.shown_route = None
        self.station_dialog: StationDialog | None = None
        self.compare_dialog: RouteCompareDialog | None = None
        self.runner = RouteRunner(graph, network, find, watchdog_ms)
        self.runner.found.connect(self.on_found)
        self.runner.failed.connect(self.on_failed)
        self.runner.slow.connect(lambda: self.statusBar().showMessage("Computing…"))
        self.setWindowTitle("Delhi Metro Route Planner")
        self.setMinimumSize(960, 600)
        self.build_widgets()
        self.build_layout()
        self.connect_signals()
        self.add_shortcuts()
        self.apply(self.state)

    # ---- construction ---------------------------------------------------------------------

    def build_widgets(self) -> None:
        """Create the side panel, the map and the controls around them (A3 [D20])."""
        self.panel = SidePanel(self.network, self.settings)
        # Short names for the panel's widgets, used by the handlers below and by the tests.
        self.from_box, self.to_box = self.panel.from_box, self.panel.to_box
        self.criterion = self.panel.criterion
        self.find_button, self.swap_button = self.panel.find_button, self.panel.swap_button
        self.reset_button = self.panel.reset_button
        self.banner, self.route_panel = self.panel.banner, self.panel.route_panel
        self.favorites = self.panel.favorites
        self.map = MapView(self.network, theme=self.theme)
        self.setStyleSheet(self.theme.stylesheet)
        self.panel_toggle = QToolButton()
        self.panel_toggle.setText("☰ Route panel")
        self.panel_toggle.setAccessibleName("Show or hide the route panel")
        self.panel_toggle.setCheckable(True)
        self.panel_toggle.setChecked(True)
        self.zoom_label = QLabel()
        self.statusBar().addPermanentWidget(self.zoom_label)

    def build_layout(self) -> None:
        """Side panel and map side by side; tab order follows the panel top to bottom."""
        right = QVBoxLayout()
        right.addWidget(self.panel_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        right.addWidget(self.map, 1)
        body = QWidget()
        row = QHBoxLayout(body)
        row.addWidget(self.panel)
        row.addLayout(right, 1)
        self.setCentralWidget(body)
        order = [*self.panel.tab_chain(), self.map]
        for a, b in zip(order, order[1:]):
            self.setTabOrder(a, b)

    def connect_signals(self) -> None:
        """Every user action goes through one handler that updates the state."""
        self.from_box.station_chosen.connect(lambda sid: self.choose("source", sid))
        self.to_box.station_chosen.connect(lambda sid: self.choose("destination", sid))
        self.from_box.cleared.connect(lambda: self.choose("source", None))
        self.to_box.cleared.connect(lambda: self.choose("destination", None))
        self.to_box.submitted.connect(self.find)
        self.from_box.submitted.connect(self.find)
        self.map.station_clicked.connect(self.on_map_click)
        self.map.station_action.connect(self.on_station_action)
        self.map.controls.theme_toggled.connect(self.toggle_theme)
        self.map.zoom_changed.connect(lambda pct: self.zoom_label.setText(f"Zoom {pct}%"))
        self.criterion.currentIndexChanged.connect(self.on_criterion)
        self.find_button.clicked.connect(self.find)
        self.swap_button.clicked.connect(self.swap)
        self.reset_button.clicked.connect(self.reset)
        self.banner.action.connect(lambda name: self.find() if name == "Retry" else self.reset())
        self.route_panel.leg_clicked.connect(self.map.focus_leg)
        self.favorites.chosen.connect(self.on_favorite)
        self.route_panel.alternative_chosen.connect(self.on_alternative)
        self.route_panel.compare_requested.connect(self.show_comparison)
        self.route_panel.export_requested.connect(self.on_export)
        self.panel_toggle.toggled.connect(self.panel.setVisible)

    def add_shortcuts(self) -> None:
        """Alt+W swaps, Alt+C focuses the criterion and Ctrl+I opens the station card.
        Esc is handled in keyPressEvent."""
        QShortcut(QKeySequence("Alt+W"), self, self.swap)
        QShortcut(QKeySequence("Alt+C"), self, self.criterion.setFocus)
        QShortcut(QKeySequence("Ctrl+I"), self, self.show_chosen_station)

    # ---- user actions -------------------------------------------------------------------------

    def choose(self, field: str, station_id: str | None) -> None:
        """A station was chosen (or cleared) in a search box; start a search if ready."""
        self.apply(st.select_station(self.state, self.network, field, station_id))
        self.find_if_ready()

    def on_map_click(self, station_id: str) -> None:
        """A map click fills From, then To, then starts again (FR4)."""
        self.apply(st.select_from_map(self.state, self.network, station_id))
        self.find_if_ready()

    def on_criterion(self, index: int) -> None:
        """Remember the criterion and recompute at once if both stations are set ([D49])."""
        self.apply(st.set_criterion(self.state, self.criterion.itemData(index)))
        self.find()  # does nothing unless both stations are valid

    def find_if_ready(self) -> None:
        """Searching starts automatically once both stations are valid (§6.5)."""
        if st.can_find(self.state, self.network)[0] and self.state.route is None:
            self.find()

    def find(self) -> None:
        """Start a search on the worker thread (FR6, FR15)."""
        ok, _ = st.can_find(self.state, self.network)
        if not ok:
            return
        self.apply(st.start_computing(self.state))
        self.runner.start(self.state.source, self.state.destination, self.state.criterion)

    def swap(self) -> None:
        """Exchange From and To and recompute if both are set."""
        self.runner.cancel()
        self.apply(st.swap(self.state))
        self.find_if_ready()

    def reset(self) -> None:
        """Cancel work and clear selection, route and messages; focus From (FR13)."""
        self.runner.cancel()
        self.apply(st.reset(self.state))
        self.from_box.field.setFocus()

    def keyPressEvent(self, event) -> None:
        """Esc resets. A key press reaches the window only if no child used it, so an Esc
        that closed a suggestion list never gets here."""
        if event.key() == Qt.Key.Key_Escape:
            self.reset()
        else:
            super().keyPressEvent(event)

    def on_found(self, route) -> None:
        """The worker finished: show the route, or the no-route message (ER7)."""
        if route is None:
            self.apply(st.route_not_found(self.state, self.network))
        else:
            self.apply(st.route_found(self.state, route, self.alternatives_for(route)))
            self.statusBar().showMessage("Route found. Map fitted to route.", 5000)

    def alternatives_for(self, route) -> tuple:
        """Other routes for the same stations. They are optional: if finding them fails, the
        route is still shown and the problem is only logged."""
        try:
            return tuple(find_alternative_routes(self.graph, self.network, route.source,
                                                 route.destination, self.state.criterion))
        except Exception:
            log.exception("Could not find alternatives for %s -> %s",
                          route.source, route.destination)
            return ()

    def on_failed(self, message: str) -> None:
        """Timeout or unexpected error: keep everything, offer Retry (ER13, ER17)."""
        self.apply(st.route_failed(self.state, message))

    # ---- drawing from the state -----------------------------------------------------------------

    def apply(self, state: st.AppState) -> None:
        """Store the new state and make every widget match it."""
        self.state = state
        for box, station in ((self.from_box, state.source), (self.to_box, state.destination)):
            if box.chosen != station:
                box.set_station(station)
        self.sync_criterion(state.criterion)
        self.show_missing_hint(self.from_box, state.destination and not state.source)
        self.show_missing_hint(self.to_box, state.source and not state.destination)
        ok, reason = st.can_find(state, self.network)
        self.find_button.setEnabled(ok)
        self.find_button.setToolTip("Find the route (Enter)" if ok else reason)
        self.banner.show_message(state.message, state.message_kind, self.banner_button(state))
        if not state.computing:
            self.statusBar().clearMessage()
        self.map.set_selection(state.source, state.destination)
        if state.route is not self.shown_route:
            self.show_route_state(state)
        route = state.route
        self.favorites.set_journey(
            Favorite(route.source, route.destination, state.criterion) if route else None)

    def show_route_state(self, state: st.AppState) -> None:
        """The route on screen changed (or went away): redraw the panel, tabs and map."""
        self.shown_route = state.route
        self.route_panel.show_route(state.route)
        self.route_panel.show_alternatives(state.alternatives, state.selected)
        if state.route is None:
            self.map.clear_route()
        else:
            self.map.show_route(state.route)

    def sync_criterion(self, criterion: str) -> None:
        """Make the Criterion box show the state's criterion (a loaded favourite may differ),
        without triggering a search of its own."""
        index = self.criterion.findData(criterion)
        if index != self.criterion.currentIndex():
            self.criterion.blockSignals(True)
            self.criterion.setCurrentIndex(index)
            self.criterion.blockSignals(False)

    def show_missing_hint(self, box: SearchBox, missing: bool) -> None:
        """ER1: "Select a source and a destination station." under the empty field."""
        if missing and not box.field.text():
            box.set_hint(st.MSG_MISSING)
        elif box.hint.text() == st.MSG_MISSING:
            box.set_hint(None)

    def banner_button(self, state: st.AppState) -> str | None:
        """The one recovery button for the banner: Retry after a failure, Reset after
        no route, otherwise none (A3 Table 12)."""
        if state.message in (st.MSG_FAILED, st.MSG_UNEXPECTED):
            return "Retry"
        return "Reset" if state.no_route else None

    # ---- window events ---------------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Below 1100 px wide the side panel collapses behind the toggle button."""
        super().resizeEvent(event)
        narrow = self.width() < NARROW_PX
        self.panel_toggle.setVisible(narrow)
        self.panel_toggle.setChecked(not narrow)

    def closeEvent(self, event) -> None:
        """Stop the worker thread before the window goes away."""
        self.runner.shutdown()
        super().closeEvent(event)
