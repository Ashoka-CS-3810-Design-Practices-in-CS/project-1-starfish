"""Cross-file validation checks (A2 Algorithm 1, checks 4, 6, 7, 8, 10, 11; ER9, ER10).

Each check is a small function that appends human-readable problems to a shared list.
Problems name the file, the entry ID and the field, e.g.
"segments.json, entry S-0412, field b: unknown station XYZ".
"""

from collections import deque

from metro.models import Line, Network, Segment, TransferData


def check_cross_references(known_ids: set[str], lines: dict[str, Line],
                           segments: list[Segment], transfers: TransferData,
                           problems: list[str]) -> None:
    """Run every check that needs more than one file."""
    check_service_stations(lines, known_ids, problems)
    check_segment_references(segments, lines, known_ids, problems)
    check_transfer_references(transfers, lines, known_ids, problems)
    check_segment_coverage(lines, segments, problems)
    check_orphan_stations(known_ids, lines, transfers, problems)


def check_service_stations(lines: dict[str, Line], known_ids: set[str],
                           problems: list[str]) -> None:
    """Every station a service lists must exist (check 4)."""
    for line in lines.values():
        for service in line.services:
            for station in service.stations:
                if station not in known_ids:
                    problems.append(f"lines.json, entry {service.id}, field stations: "
                                    f"unknown station {station}")


def check_segment_references(segments: list[Segment], lines: dict[str, Line],
                             known_ids: set[str], problems: list[str]) -> None:
    """Every segment must name a known line and two known stations (check 4)."""
    for seg in segments:
        if seg.line_id not in lines:
            problems.append(f"segments.json, entry {seg.id}, field line: "
                            f"unknown line {seg.line_id}")
        for name, station in (("a", seg.a), ("b", seg.b)):
            if station not in known_ids:
                problems.append(f"segments.json, entry {seg.id}, field {name}: "
                                f"unknown station {station}")


def check_transfer_references(transfers: TransferData, lines: dict[str, Line],
                              known_ids: set[str], problems: list[str]) -> None:
    """Overrides, no-transfer pairs and walkways must name known IDs (checks 4 and 10)."""
    file = "transfers.json"
    services = {s.id: s for line in lines.values() for s in line.services}
    for i, ov in enumerate(transfers.overrides):
        label = f"{file}, entry override #{i}"
        if ov.station not in known_ids:
            problems.append(f"{label}, field station: unknown station {ov.station}")
        for name, sid in (("service_a", ov.service_a), ("service_b", ov.service_b)):
            if sid not in services:
                problems.append(f"{label}, field {name}: unknown service {sid}")
            elif ov.station in known_ids and ov.station not in services[sid].stations:
                problems.append(f"{label}, field {name}: service {sid} "
                                f"does not serve {ov.station}")  # check 10
    for i, pair in enumerate(transfers.no_transfer):
        for sid in pair:
            if sid not in services:
                problems.append(f"{file}, entry no_transfer #{i}: unknown service {sid}")
    for walk in transfers.walkways:
        for name, station in (("a", walk.a), ("b", walk.b)):
            if station not in known_ids:
                problems.append(f"{file}, entry {walk.id}, field {name}: "
                                f"unknown station {station}")


def consecutive_pairs(stations: tuple[str, ...], loop: bool) -> list[tuple[str, str]]:
    """Adjacent station pairs of a service, plus last -> first for a loop."""
    pairs = list(zip(stations, stations[1:]))
    if loop and len(stations) > 2:
        pairs.append((stations[-1], stations[0]))
    return pairs


def check_segment_coverage(lines: dict[str, Line], segments: list[Segment],
                           problems: list[str]) -> None:
    """Each service hop needs a segment on its line (check 6); each segment needs a hop (7)."""
    by_key: dict[tuple[str, frozenset[str]], Segment] = {}
    for seg in segments:
        key = (seg.line_id, frozenset((seg.a, seg.b)))
        if key in by_key:
            problems.append(f"segments.json, entry {seg.id}, field a/b: same line and stations "
                            f"as {by_key[key].id}")  # a duplicate in all but ID (check 3)
        by_key.setdefault(key, seg)
    used: set[tuple[str, frozenset[str]]] = set()
    for line in lines.values():
        for service in line.services:
            for a, b in consecutive_pairs(service.stations, service.loop):
                key = (line.id, frozenset((a, b)))
                used.add(key)
                if key not in by_key:
                    problems.append(f"lines.json, entry {service.id}, field stations: "
                                    f"no {line.id} segment between {a} and {b}")
    for key, seg in by_key.items():
        if key not in used:
            problems.append(f"segments.json, entry {seg.id}, field a/b: "
                            "segment is used by no service")


def check_orphan_stations(known_ids: set[str], lines: dict[str, Line],
                          transfers: TransferData, problems: list[str]) -> None:
    """Every station must be on a service or in a walkway (check 8)."""
    reached = {st for line in lines.values() for s in line.services for st in s.stations}
    reached |= {st for w in transfers.walkways for st in (w.a, w.b)}
    for station in sorted(known_ids - reached):
        problems.append(f"stations.json, entry {station}: station is on no service "
                        "and in no walkway")


def is_connected(network: Network) -> bool:
    """True if every station can reach every other by train or walkway (check 11, UC5).

    Uses breadth-first search on an undirected station graph; closures are ignored
    because they are a property of the day, not of the network's shape.
    """
    neighbours: dict[str, set[str]] = {sid: set() for sid in network.stations}
    links = [pair for s in network.services.values()
             for pair in consecutive_pairs(s.stations, s.loop)]
    links += [(w.a, w.b) for w in network.walkways]
    for a, b in links:
        neighbours[a].add(b)
        neighbours[b].add(a)
    if not neighbours:
        return True
    start = next(iter(neighbours))
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in neighbours[queue.popleft()]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return len(seen) == len(neighbours)
