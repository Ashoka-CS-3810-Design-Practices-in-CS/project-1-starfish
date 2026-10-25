"""AppState tests (T15, T16, TM12; FR4, FR5, FR13, ER1, ER5–ER7, ER13, ER17, [D33])."""

from conftest import TOY_METRO, close_stations

from metro.app_state import (
    MSG_FAILED,
    MSG_MISSING,
    MSG_SAME,
    AppState,
    can_find,
    choose_alternative,
    load_route,
    reset,
    route_failed,
    route_found,
    route_not_found,
    select_destination,
    select_from_map,
    select_source,
    set_criterion,
    show_message,
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


# ---- alternatives, saved routes and messages ([D47]–[D49]) ------------------------------


def two_routes():
    """TM2 (fastest) and TM6 (fewest stops) for A -> F."""
    graph = build_graph(NET)
    return find_route(graph, NET, "A", "F"), find_route(graph, NET, "A", "F", "fewest_stops")


def test_route_found_puts_the_shown_route_first_without_duplicates():
    """The alternatives list starts with the route on screen and lists each route once."""
    fast, few = two_routes()
    state = route_found(ready(), few, (fast, few, fast))
    assert state.route == few and state.alternatives == (few, fast)
    assert state.selected == 0


def test_choose_alternative_switches_the_route_and_keeps_the_list():
    """Choosing index 1 shows the second route; the list stays so the user can go back."""
    fast, few = two_routes()
    state = choose_alternative(route_found(ready(), fast, (fast, few)), 1)
    assert state.route == few and state.alternatives == (fast, few) and state.selected == 1


def test_choose_alternative_ignores_a_bad_index():
    """Out-of-range indexes (stale clicks) change nothing."""
    fast, few = two_routes()
    state = route_found(ready(), fast, (fast, few))
    assert choose_alternative(state, 5) is state and choose_alternative(state, -1) is state


def test_choosing_stations_or_swapping_clears_the_alternatives():
    """The old alternatives belong to the old stations."""
    fast, few = two_routes()
    shown = route_found(ready(), fast, (fast, few))
    assert select_destination(shown, NET, "E").alternatives == ()
    assert swap(shown).alternatives == ()
    assert route_not_found(shown, NET).alternatives == ()


def test_load_route_sets_everything_and_clears_the_route():
    """A saved favourite fills both stations and the criterion; a search is still needed."""
    fast, _ = two_routes()
    state = load_route(route_found(ready(), fast), NET, "B", "E", "fewest_stops")
    assert (state.source, state.destination, state.criterion) == ("B", "E", "fewest_stops")
    assert state.route is None and state.message is None
    assert can_find(state, NET) == (True, "")


def test_load_route_refuses_a_closed_station_and_changes_nothing_else():
    """ER6 applies to a favourite whose station has since closed."""
    before = ready()
    state = load_route(before, CLOSED_C, "C", "E", "fastest")
    assert state.message == "Station Station C is closed and cannot be used."
    assert (state.source, state.destination) == ("A", "F") and state.message_kind == "error"


def test_show_message_only_changes_the_message():
    """Used for export problems: the route and selection stay."""
    fast, _ = two_routes()
    shown = route_found(ready(), fast)
    state = show_message(shown, "Could not save.", "error")
    assert state.message == "Could not save." and state.message_kind == "error"
    assert state.route == fast and state.source == "A"
