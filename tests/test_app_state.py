"""AppState tests (T15, T16, TM12; FR4, FR5, FR13, ER1, ER5–ER7, ER13, ER17, [D33])."""

from conftest import TOY_METRO, close_stations

from metro.app_state import (
    MSG_FAILED,
    MSG_MISSING,
    MSG_SAME,
    AppState,
    can_find,
    reset,
    route_failed,
    route_found,
    route_not_found,
    select_destination,
    select_from_map,
    select_source,
    set_criterion,
    start_computing,
    swap,
)
from metro.data import load_network
from metro.graph import build_graph
from metro.router import find_route

NET = load_network(TOY_METRO)
CLOSED_C = close_stations(NET, "C")


def ready(src="A", dst="F") -> AppState:
    """A state with both stations chosen."""
    return select_destination(select_source(AppState(), NET, src), NET, dst)


# ---- T15: validation before any search runs ---------------------------------------------


def test_t15_missing_input_disables_find():
    """ER1: Find is disabled with a reason until both stations are chosen."""
    assert can_find(AppState(), NET) == (False, MSG_MISSING)
    assert can_find(select_source(AppState(), NET, "A"), NET) == (False, MSG_MISSING)
    assert can_find(ready(), NET) == (True, "")


def test_tm12_same_station_is_refused():
    """TM12/ER5: A->A gives the same-station message and can_find is false."""
    state = ready("A", "A")
    assert state.message == MSG_SAME and state.message_kind == "error"
    assert can_find(state, NET) == (False, MSG_SAME)


def test_t15_closed_station_is_refused():
    """ER6: choosing a closed station shows a message and keeps the old choice."""
    state = select_source(AppState(), CLOSED_C, "A")
    state = select_source(state, CLOSED_C, "C")
    assert state.source == "A"
    assert state.message == "Station Station C is closed and cannot be used."


# ---- T16: phases and transitions ------------------------------------------------------------


def test_t16_phase_follows_the_fields():
    """The phase is derived: Idle -> Partial -> Ready -> Computing -> RouteShown."""
    route = find_route(build_graph(NET), NET, "A", "F")
    assert AppState().phase == "Idle"
    assert select_source(AppState(), NET, "A").phase == "Partial"
    assert ready().phase == "Ready"
    assert start_computing(ready()).phase == "Computing"
    assert route_found(start_computing(ready()), route).phase == "RouteShown"


def test_t16_no_route_and_errors():
    """ER7 sets NoRoute with its message; ER13 keeps the route that was already shown."""
    state = route_not_found(start_computing(ready("A", "D")), NET)
    assert state.phase == "NoRoute"
    assert state.message == ("No route found between Station A and Station D "
                             "with the current closures.")
    route = find_route(build_graph(NET), NET, "A", "F")
    shown = route_found(ready(), route)
    failed = route_failed(start_computing(shown), MSG_FAILED)
    assert failed.route == route and failed.message == MSG_FAILED
    assert failed.source == "A" and failed.destination == "F"


def test_t16_reset_swap_and_criterion():
    """Reset clears everything but the criterion; swap exchanges and clears the route."""
    route = find_route(build_graph(NET), NET, "A", "F")
    shown = route_found(set_criterion(ready(), "fewest_stops"), route)
    assert reset(shown) == AppState(criterion="fewest_stops")
    swapped = swap(shown)
    assert (swapped.source, swapped.destination, swapped.route) == ("F", "A", None)


def test_new_selection_replaces_the_route():
    """Choosing another station is the user's own action, so the old route goes."""
    route = find_route(build_graph(NET), NET, "A", "F")
    state = select_destination(route_found(ready(), route), NET, "E")
    assert state.route is None and state.phase == "Ready"


def test_map_clicks_fill_source_then_destination_then_restart():
    """FR4: click 1 sets the source, click 2 the destination, click 3 a new source."""
    state = select_from_map(AppState(), NET, "A")
    state = select_from_map(state, NET, "F")
    assert (state.source, state.destination) == ("A", "F")
    state = select_from_map(state, NET, "E")
    assert (state.source, state.destination) == ("E", None)


def test_updates_never_mutate():
    """Every update returns a new value; the old one is unchanged."""
    before = ready()
    swap(before)
    reset(before)
    assert (before.source, before.destination) == ("A", "F")
