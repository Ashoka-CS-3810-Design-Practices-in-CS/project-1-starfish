"""The optional features of the main window, as methods it inherits (Could tier).

Favourites, route tabs and comparison, export, the theme toggle and the station card are
handlers that only turn a user action into an AppState update, a dialog or a setting. They
live here so `main_window.py` stays under the project's 300-line limit. `ExtrasMixin` is not
usable on its own: it relies on the window's `state`, `apply`, `choose`, `network`, `map`,
`settings`, `runner` and `find_if_ready`.
"""

from metro import app_state as st
from metro.ui.compare_dialog import RouteCompareDialog
from metro.ui.export import export_route
from metro.ui.station_dialog import StationDialog
from metro.ui.theme import Theme, other_theme


class ExtrasMixin:
    """Handlers for favourites, alternatives, export, theme and the station card."""

    def on_favorite(self, source: str, destination: str, criterion: str) -> None:
        """A saved route was picked: fill both stations and the criterion, then search."""
        self.runner.cancel()
        self.apply(st.load_route(self.state, self.network, source, destination, criterion))
        self.find_if_ready()

    def on_export(self, kind: str) -> None:
        """Copy or save the route on screen; a failure goes to the banner, never a crash."""
        if self.state.route is None:
            return
        outcome = export_route(self, self.network, self.state.route, kind)
        if outcome is None:  # the user cancelled the file dialog
            return
        level, message = outcome
        if level == "error":
            self.apply(st.show_message(self.state, message, "error"))
        else:
            self.statusBar().showMessage(message, 5000)

    def on_alternative(self, index: int) -> None:
        """A route tab (or the comparison) picked another route for the same journey."""
        self.apply(st.choose_alternative(self.state, index))

    def show_comparison(self) -> None:
        """Open the side-by-side comparison when there is more than one route ([D56])."""
        if len(self.state.alternatives) < 2:
            return
        dialog = RouteCompareDialog(self.network, self.state.alternatives, self.state.selected,
                                    self)
        dialog.route_chosen.connect(self.on_alternative)
        self.compare_dialog = dialog
        dialog.show()

    def toggle_theme(self) -> None:
        """The map's theme button: light becomes dark and the other way round."""
        self.set_theme(other_theme(self.theme))

    def set_theme(self, theme: Theme) -> None:
        """Restyle the window and the map, and remember the choice for next time ([D55])."""
        self.theme = theme
        self.setStyleSheet(theme.stylesheet)
        self.map.set_theme(theme)
        self.settings.setValue("theme", theme.name)

    def on_station_action(self, action: str, station_id: str) -> None:
        """A choice from the map's station menu: open the card or fill a field."""
        if action == "details":
            self.show_station(station_id)
        else:
            self.choose("source" if action == "from" else "destination", station_id)

    def show_station(self, station_id: str) -> None:
        """Open the station card; its buttons fill From or To ([D54])."""
        dialog = StationDialog(self.network, station_id, self)
        dialog.set_as_from.connect(lambda sid: self.choose("source", sid))
        dialog.set_as_to.connect(lambda sid: self.choose("destination", sid))
        self.station_dialog = dialog
        dialog.show()

    def show_chosen_station(self) -> None:
        """Ctrl+I: the card of the To station, else the From station (keyboard route to it)."""
        station = self.state.destination or self.state.source
        if station is None:
            self.statusBar().showMessage("Choose a station first, then press Ctrl+I.", 4000)
        else:
            self.show_station(station)
