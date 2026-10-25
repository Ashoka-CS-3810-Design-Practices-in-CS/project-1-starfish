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


def route_steps(route: Route) -> list[Leg | Interchange]:
    """Legs and interchanges in the order a traveller meets them: a change sits between two
    rides, never before the first or after the last."""
    steps: list[Leg | Interchange] = []
    changes = iter(route.interchanges)
    rides = 0
    for leg in route.legs:
        if leg.kind == "RIDE":
            if rides > 0:
                steps.append(next(changes))
            rides += 1
        steps.append(leg)
    return steps


def leg_station_names(network: Network, leg: Leg) -> list[str]:
    """Names of every station a leg visits in travel order, boarding and alighting included."""
    return [station_name(network, sid) for sid in leg.stations]


def between_names(network: Network, leg: Leg) -> list[str]:
    """The stations passed through without getting off: all but the first and last."""
    return leg_station_names(network, leg)[1:-1]


def route_lines(network: Network, route: Route, expand: bool = False) -> list[str]:
    """The whole route as lines of text: summary, then legs and interchanges in order.

    With `expand`, each ride lists the stations it passes through, one per line.
    """
    out = [summary_text(route)]
    number = 0
    for step in route_steps(route):
        if isinstance(step, Interchange):
            out.append("   " + interchange_text(network, step))
            continue
        number += 1
        out.append(f"{number}. {leg_text(network, step)}")
        if expand:
            out += [f"     · {name}" for name in between_names(network, step)]
    return out


def route_title(network: Network, route: Route) -> str:
    """'Rajiv Chowk → Hauz Khas'."""
    return f"{station_name(network, route.source)} → {station_name(network, route.destination)}"


def export_route_text(network: Network, route: Route, format: str = "txt") -> str:
    """The route as a document to save or paste: plain text ("txt") or Markdown ("md").

    Both list every intermediate station. An unknown format is a programming error.
    """
    if format == "txt":
        return "\n".join([route_title(network, route), *route_lines(network, route, True)]) + "\n"
    if format == "md":
        return export_markdown(network, route)
    raise ValueError(f"Unknown export format {format!r}; use 'txt' or 'md'.")


def export_markdown(network: Network, route: Route) -> str:
    """Markdown version of the route: a heading, the summary in bold, a numbered list.

    A change is its own italic paragraph between the legs; the legs keep their explicit
    numbers, which Markdown renderers honour when a list restarts."""
    out = [f"# {route_title(network, route)}", "", f"**{summary_text(route)}**", ""]
    number = 0
    for step in route_steps(route):
        if isinstance(step, Interchange):
            out += ["", f"*{interchange_text(network, step)}*", ""]
            continue
        number += 1
        out.append(f"{number}. {leg_text(network, step)}")
        out += [f"   - {name}" for name in between_names(network, step)]
    return "\n".join(out) + "\n"


def station_lines(network: Network) -> dict[str, list[str]]:
    """For each station, the names of the lines that stop there, in line-ID order."""
    lines: dict[str, list[str]] = {sid: [] for sid in network.stations}
    for line in network.lines.values():
        for station in sorted({st for s in line.services for st in s.stations}):
            lines[station].append(line.name)
    return lines


def station_tooltip(network: Network, station_id: str, lines: list[str]) -> str:
    """Hover text: name, code, lines, and badges for interchanges and closures (FR12)."""
    st = network.stations[station_id]
    text = f"{st.name} ({st.id})\n" + (", ".join(lines) if lines else "No line")
    if len(lines) > 1:
        text += "\nInterchange"
    if st.closed:
        text += "\nClosed"
    return text
