"""Immutable data types shared by the whole app (A2 data model; PRD §4.1, §5.3).

Network-side types describe the input data. Route-side types describe a search result.
"""

from dataclasses import dataclass

# ---- network ------------------------------------------------------------------


@dataclass(frozen=True)
class Station:
    """A physical place, such as Rajiv Chowk. `id` is also the code users can search for."""

    id: str
    name: str
    lat: float
    lon: float
    aliases: tuple[str, ...] = ()
    closed: bool = False
    verified: bool = True


@dataclass(frozen=True)
class Service:
    """One continuous train path on a line. A loop service also runs last -> first."""

    id: str
    line_id: str
    stations: tuple[str, ...]
    loop: bool = False


@dataclass(frozen=True)
class Line:
    """A coloured DMRC line, made of one or more services."""

    id: str
    name: str
    color: str
    services: tuple[Service, ...]


@dataclass(frozen=True)
class Segment:
    """Running time between two adjacent stations on a line, same both ways ([A4])."""

    id: str
    line_id: str
    a: str
    b: str
    time_s: int


@dataclass(frozen=True)
class Walkway:
    """A walk between two different stations ([D2])."""

    id: str
    a: str
    b: str
    time_s: int
    one_way: bool = False


@dataclass(frozen=True)
class TransferOverride:
    """A custom transfer time for one station and one service pair, both directions."""

    station: str
    service_a: str
    service_b: str
    time_s: int


@dataclass(frozen=True)
class TransferData:
    """The parsed contents of transfers.json, used only while loading."""

    default_other_line_s: int
    default_same_line_s: int
    overrides: tuple[TransferOverride, ...]
    no_transfer: tuple[tuple[str, str], ...]
    walkways: tuple[Walkway, ...]


@dataclass(frozen=True)
class Network:
    """The whole validated dataset. Every collection is in sorted-ID order ([D4])."""

    stations: dict[str, Station]
    lines: dict[str, Line]
    services: dict[str, Service]
    segments: tuple[Segment, ...]
    walkways: tuple[Walkway, ...]
    default_other_line_s: int
    default_same_line_s: int
    overrides: tuple[TransferOverride, ...]
    no_transfer: frozenset[frozenset[str]]


# ---- route --------------------------------------------------------------------


@dataclass(frozen=True)
class Leg:
    """One part of a journey: a RIDE on one service, or a WALK at the start or end."""

    kind: str  # "RIDE" or "WALK"
    line_id: str | None  # None for WALK
    service_id: str | None
    stations: tuple[str, ...]  # boarding .. alighting (2 stations for a WALK)
    time_s: int
    direction: str | None  # "towards <station name>"


@dataclass(frozen=True)
class Interchange:
    """A change between two RIDE legs: a transfer at one station, or a walk between two."""

    at_station: str  # where you get off
    to_station: str  # same as at_station unless is_walk
    from_line: str
    to_line: str
    time_s: int
    is_walk: bool


@dataclass(frozen=True)
class Route:
    """A complete answer to a route query (A2 Alg. 4)."""

    source: str
    destination: str
    legs: tuple[Leg, ...]
    interchanges: tuple[Interchange, ...]
    total_s: int
    stops: int  # number of ride arcs
