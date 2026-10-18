"""What the UI should show, as one immutable value plus pure update functions [D33].

There is no transition table: `phase` is derived from the fields, so an impossible state
(say, "computing" and "no route" at once with nothing selected) cannot be described.
Every function returns a new AppState and never changes the one it was given.
"""

from dataclasses import dataclass, replace

from metro.models import Network, Route

MSG_MISSING = "Select a source and a destination station."  # ER1
MSG_SAME = "Choose two different stations."  # ER5
MSG_FAILED = "Route calculation failed."  # ER13
MSG_UNEXPECTED = "Something went wrong. Your selection was kept."  # ER17


@dataclass(frozen=True)
class AppState:
    """Everything the window needs to draw itself."""

    source: str | None = None
    destination: str | None = None
    criterion: str = "fastest"
    route: Route | None = None
    computing: bool = False
    message: str | None = None  # banner text
    message_kind: str | None = None  # "error" or "info"
    no_route: bool = False

    @property
    def phase(self) -> str:
        """Idle, Partial, Ready, Computing, RouteShown or NoRoute, worked out from the fields."""
        if self.computing:
            return "Computing"
        if self.route is not None:
            return "RouteShown"
        if self.no_route:
            return "NoRoute"
        if self.source and self.destination:
            return "Ready"
        return "Partial" if self.source or self.destination else "Idle"


def closed_message(network: Network, station_id: str) -> str:
    """ER6 text for a closed station."""
    return f"Station {network.stations[station_id].name} is closed and cannot be used."


def select_station(state: AppState, network: Network, field: str,
                   station_id: str | None) -> AppState:
    """Set (or clear, with None) the "source" or "destination" (FR4, FR5).

    A closed station is refused with the ER6 message and the old choice is kept. Choosing
    a station is the user's own action, so it replaces any route on screen.
    """
    if station_id is not None and network.stations[station_id].closed:
        return replace(state, message=closed_message(network, station_id), message_kind="error")
    new = replace(state, route=None, no_route=False, message=None, message_kind=None,
                  **{field: station_id})
    if new.source is not None and new.source == new.destination:
        return replace(new, message=MSG_SAME, message_kind="error")  # ER5
    return new


def select_source(state: AppState, network: Network, station_id: str | None) -> AppState:
    """Choose or clear the source station."""
    return select_station(state, network, "source", station_id)


def select_destination(state: AppState, network: Network, station_id: str | None) -> AppState:
    """Choose or clear the destination station."""
    return select_station(state, network, "destination", station_id)


def select_from_map(state: AppState, network: Network, station_id: str) -> AppState:
    """A map click (FR4): fills the source first, then the destination; when both are
    already set, it starts again with a new source and no destination."""
    if state.source is None:
        return select_source(state, network, station_id)
    if state.destination is None:
        return select_destination(state, network, station_id)
    return select_source(select_destination(state, network, None), network, station_id)


def set_criterion(state: AppState, criterion: str) -> AppState:
    """Change the criterion; the route on screen stays until Find recomputes it."""
    return replace(state, criterion=criterion)


def swap(state: AppState) -> AppState:
    """Exchange source and destination; the old route no longer matches, so clear it."""
    return replace(state, source=state.destination, destination=state.source, route=None,
                   no_route=False, message=None, message_kind=None)


def reset(state: AppState) -> AppState:
    """Clear selection, route and messages (FR13); the chosen criterion is kept."""
    return AppState(criterion=state.criterion)


def can_find(state: AppState, network: Network) -> tuple[bool, str]:
    """Whether Find is allowed, and if not, the reason (shown as the button's tooltip)."""
    if state.source is None or state.destination is None:
        return False, MSG_MISSING
    if state.source == state.destination:
        return False, MSG_SAME
    for station_id in (state.source, state.destination):
        if network.stations[station_id].closed:
            return False, closed_message(network, station_id)
    return True, ""


def start_computing(state: AppState) -> AppState:
    """A search has started. A route already on screen stays visible meanwhile."""
    return replace(state, computing=True, message=None, message_kind=None)


def route_found(state: AppState, route: Route) -> AppState:
    """The search succeeded."""
    return replace(state, computing=False, route=route, no_route=False,
                   message=None, message_kind=None)


def route_not_found(state: AppState, network: Network) -> AppState:
    """The search finished without a route (ER7)."""
    names = [network.stations[s].name for s in (state.source, state.destination)]
    return replace(state, computing=False, route=None, no_route=True, message_kind="info",
                   message=f"No route found between {names[0]} and {names[1]} "
                           "with the current closures.")


def route_failed(state: AppState, message: str) -> AppState:
    """The search timed out or crashed (ER13, ER17); the selection and any route stay."""
    return replace(state, computing=False, message=message, message_kind="error")
