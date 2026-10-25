"""Command-line walking skeleton: route any pair of stations and print the result.

The optional last argument is the criterion: fastest, fewest_changes or fewest_stops.
Add --stations anywhere to list every station each ride passes through.

Usage: python tools/route_cli.py data "Rajiv Chowk" "Hauz Khas" [criterion] [--stations]
"""

import sys

from metro.console import use_utf8_output
from metro.data import load_network
from metro.describe import route_lines
from metro.errors import DataError, DatasetUnreadable
from metro.graph import build_graph
from metro.router import KEY_FUNCTIONS, find_route
from metro.search import build_index, search


def pick_station(index, text: str) -> str | None:
    """The station for `text` if the best match is exact (code or name); else print hints."""
    matches = search(index, text)
    if matches and matches[0].match_type in ("CODE", "NAME"):
        return matches[0].station_id
    if not matches:
        print(f"No station matches '{text}'.")
    else:
        print(f"'{text}' is not exact. Did you mean: " + ", ".join(m.name for m in matches) + "?")
    return None


def main(argv: list[str]) -> int:
    """Run one query from the command line; return the process exit code."""
    use_utf8_output()  # a Windows console in cp1252 cannot print → and ⇒
    expand = "--stations" in argv
    argv = [a for a in argv if a != "--stations"]
    if len(argv) not in (4, 5) or (len(argv) == 5 and argv[4] not in KEY_FUNCTIONS):
        print(__doc__.strip().splitlines()[-1])
        return 2
    try:
        network = load_network(argv[1])
    except DatasetUnreadable as exc:
        print(f"Cannot read the data: {exc}")
        return 1
    except DataError as exc:
        print(f"The network data has {len(exc.problems)} problems:")
        print("\n".join(exc.problems[:10]))
        return 1
    index = build_index(network.stations.values())
    src, dst = pick_station(index, argv[2]), pick_station(index, argv[3])
    if src is None or dst is None:
        return 1
    criterion = argv[4] if len(argv) == 5 else "fastest"
    route = find_route(build_graph(network), network, src, dst, criterion)
    names = f"{network.stations[src].name} and {network.stations[dst].name}"
    if route is None:
        print(f"No route found between {names} with the current closures.")
        return 1
    print(f"{network.stations[src].name} → {network.stations[dst].name}")
    print("\n".join(route_lines(network, route, expand)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
