"""Favourite routes: a short list of (from, to, criterion) kept between runs (Could tier,
FR18–FR21, ER15–ER16, [D48]).

Pure functions on immutable values. The UI stores the text from `encode` in QSettings and
gives it back to `decode`, which never raises: a damaged saved list must not stop start-up.
"""

import json
from dataclasses import dataclass

from metro.describe import CRITERION_LABELS, station_name
from metro.models import Network

MAX_FAVORITES = 20


@dataclass(frozen=True)
class Favorite:
    """One saved journey."""

    source: str
    destination: str
    criterion: str = "fastest"


def encode(favorites: tuple[Favorite, ...]) -> str:
    """The list as JSON text."""
    return json.dumps([{"from": f.source, "to": f.destination, "criterion": f.criterion}
                       for f in favorites])


def decode(text: str | None, network: Network) -> tuple[Favorite, ...]:
    """The saved list, keeping only entries that still make sense on this network.

    Anything unreadable gives an empty list. An entry is dropped if it is malformed, names a
    station the data no longer has, has two equal stations, or has an unknown criterion.
    """
    try:
        raw = json.loads(text)
    except (TypeError, ValueError):
        return ()
    if not isinstance(raw, list):
        return ()
    found: list[Favorite] = []
    for entry in raw:
        favorite = parse_entry(entry, network)
        if favorite is not None and favorite not in found:
            found.append(favorite)
    return tuple(found[:MAX_FAVORITES])


def parse_entry(entry: object, network: Network) -> Favorite | None:
    """One favourite from decoded JSON, or None if it is not valid."""
    if not isinstance(entry, dict):
        return None
    source, destination = entry.get("from"), entry.get("to")
    criterion = entry.get("criterion", "fastest")
    if not all(isinstance(x, str) for x in (source, destination, criterion)):
        return None
    if source not in network.stations or destination not in network.stations:
        return None
    if source == destination or criterion not in CRITERION_LABELS:
        return None
    return Favorite(source, destination, criterion)


def toggle(favorites: tuple[Favorite, ...], favorite: Favorite) -> tuple[Favorite, ...]:
    """Remove the favourite if it is saved; otherwise add it at the front.

    The list keeps the newest MAX_FAVORITES entries, so it cannot grow without bound.
    """
    if favorite in favorites:
        return tuple(f for f in favorites if f != favorite)
    return ((favorite, *favorites))[:MAX_FAVORITES]


def label(network: Network, favorite: Favorite) -> str:
    """'Rajiv Chowk → Hauz Khas · Fastest', the text of a menu entry."""
    return (f"{station_name(network, favorite.source)} → "
            f"{station_name(network, favorite.destination)} · "
            f"{CRITERION_LABELS[favorite.criterion]}")
