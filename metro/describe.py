"""Plain-text descriptions of a Route, shared by the CLI and the route panel (FR7, FR8).

Minutes are always rounded from seconds, never added up from rounded leg minutes (§5.3).
"""

from metro.models import Interchange, Leg, Network, Route
from metro.router import minutes


def plural(n: int, word: str) -> str:
    """'1 stop', '2 stops'; 'interchange' likewise."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def summary_text(route: Route) -> str:
    """'Estimated 57 min · 1 interchange · 31 stops'."""
    return (f"Estimated {minutes(route.total_s)} min · "
            f"{plural(len(route.interchanges), 'interchange')} · {plural(route.stops, 'stop')}")


def station_name(network: Network, station_id: str) -> str:
    """The display name of a station."""
    return network.stations[station_id].name


def leg_text(network: Network, leg: Leg) -> str:
    """'Yellow Line towards X: A → B (12 min)' or 'Walk A → B (5 min)'."""
    start = station_name(network, leg.stations[0])
    end = station_name(network, leg.stations[-1])
    if leg.kind == "WALK":
        return f"Walk {start} → {end} ({minutes(leg.time_s)} min)"
    line = network.lines[leg.line_id].name
    return f"{line} {leg.direction}: {start} → {end} ({minutes(leg.time_s)} min)"


def interchange_text(network: Network, ic: Interchange) -> str:
    """'⇒ Change at X (4 min)' or '⇒ Walk from X to Y (5 min)'."""
    at = station_name(network, ic.at_station)
    mins = minutes(ic.time_s)
    if ic.is_walk:
        return f"⇒ Walk from {at} to {station_name(network, ic.to_station)} ({mins} min)"
    return f"⇒ Change at {at} ({mins} min)"


def route_lines(network: Network, route: Route) -> list[str]:
    """The whole route as lines of text: summary, then legs and interchanges in order."""
    out = [summary_text(route)]
    changes = iter(route.interchanges)
    ride_count = 0
    for number, leg in enumerate(route.legs, start=1):
        if leg.kind == "RIDE":
            if ride_count > 0:
                out.append("   " + interchange_text(network, next(changes)))
            ride_count += 1
        out.append(f"{number}. {leg_text(network, leg)}")
    return out
