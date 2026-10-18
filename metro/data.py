"""Load the four JSON files and turn them into a Network (A2 Algorithm 1; FR1, ER8–ER10).

Parsing checks the shape of each entry (missing fields, wrong types, duplicate IDs, ranges).
The cross-file checks live in `validate.py`. Every check appends to one shared `problems`
list, so the user sees every problem at once instead of fixing them one by one.
"""

import json
import logging
from pathlib import Path

from metro.errors import DataError, DatasetUnreadable
from metro.models import (
    Line,
    Network,
    Segment,
    Service,
    Station,
    TransferData,
    TransferOverride,
    Walkway,
)
from metro.validate import check_cross_references, is_connected

log = logging.getLogger(__name__)

MIN_TIME_S = 10
MAX_TIME_S = 600
LAT_RANGE = (28.0, 29.0)  # the NCR box
LON_RANGE = (76.7, 77.8)


def load_network(folder: str | Path) -> Network:
    """Read and validate the dataset in `folder` and return a Network (FR1).

    Raises DatasetUnreadable for a missing or broken file, DataError listing every problem.
    """
    folder = Path(folder)
    raw = {name: read_json(folder / name) for name in
           ("stations.json", "lines.json", "segments.json", "transfers.json")}
    problems: list[str] = []
    stations, known_ids = parse_stations(raw["stations.json"], problems)
    lines = parse_lines(raw["lines.json"], problems)
    segments = parse_segments(raw["segments.json"], problems)
    transfers = parse_transfers(raw["transfers.json"], problems)
    check_cross_references(known_ids, lines, segments, transfers, problems)
    if problems:
        raise DataError(problems)

    services = sorted((s for line in lines.values() for s in line.services), key=lambda s: s.id)
    network = Network(
        stations=stations,
        lines=lines,
        services={s.id: s for s in services},
        segments=tuple(segments),
        walkways=tuple(transfers.walkways),
        default_other_line_s=transfers.default_other_line_s,
        default_same_line_s=transfers.default_same_line_s,
        overrides=tuple(transfers.overrides),
        no_transfer=frozenset(frozenset(pair) for pair in transfers.no_transfer),
    )
    if not is_connected(network):
        log.warning("The network is disconnected: some stations cannot reach others (UC5).")
    return network


def read_json(path: Path):
    """Parse one JSON file, or raise DatasetUnreadable (check 1, ER8)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise DatasetUnreadable(str(path), "file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise DatasetUnreadable(str(path), f"cannot read file ({exc})") from None
    except json.JSONDecodeError as exc:
        raise DatasetUnreadable(str(path), f"not valid JSON ({exc})") from None


# ---- generic field checks ---------------------------------------------------------


def has_kind(value, kind: str) -> bool:
    """True if `value` is of the JSON kind named: str, int, number, bool, list or list[str]."""
    if isinstance(value, bool):
        return kind == "bool"  # bool is a subclass of int in Python, so test it first
    if kind == "number":
        return isinstance(value, (int, float))
    if kind == "list[str]":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    return isinstance(value, {"str": str, "int": int, "list": list}.get(kind, ()))


def check_fields(file: str, label: str, entry, required: dict, optional: dict,
                 problems: list[str]) -> bool:
    """Report missing or wrongly typed fields of one entry (check 2); True if usable."""
    if not isinstance(entry, dict):
        problems.append(f"{file}, entry {label}: expected an object")
        return False
    ok = True
    for name in required:
        if name not in entry:
            problems.append(f"{file}, entry {label}, field {name}: missing")
            ok = False
    for name, kind in (required | optional).items():
        if name in entry and not has_kind(entry[name], kind):
            problems.append(f"{file}, entry {label}, field {name}: expected {kind}")
            ok = False
    return ok


def entry_label(entry, index: int) -> str:
    """The name used for an entry in messages: its `id` if it has one, else `#index`."""
    if isinstance(entry, dict) and isinstance(entry.get("id"), str):
        return entry["id"]
    return f"#{index}"


def check_duplicate(file: str, entry_id: str, seen: set[str], problems: list[str]) -> None:
    """Report an ID that was already seen in the same file (check 3)."""
    if entry_id in seen:
        problems.append(f"{file}, entry {entry_id}, field id: duplicate ID")
    seen.add(entry_id)


def check_time(file: str, label: str, name: str, value: int, problems: list[str]) -> None:
    """Report a time outside 10..600 s; the bounds themselves are accepted (check 5)."""
    if value < MIN_TIME_S:
        problems.append(f"{file}, entry {label}, field {name}: {value} (min {MIN_TIME_S})")
    elif value > MAX_TIME_S:
        problems.append(f"{file}, entry {label}, field {name}: {value} (max {MAX_TIME_S})")


def as_list(raw, file: str, problems: list[str]) -> list:
    """Return `raw` if it is a JSON array; otherwise report it and return []."""
    if isinstance(raw, list):
        return raw
    problems.append(f"{file}: expected a list at the top level")
    return []


# ---- one parser per file ----------------------------------------------------------


def parse_stations(raw, problems: list[str]) -> tuple[dict[str, Station], set[str]]:
    """Parse stations.json; also return every well-formed ID, even of broken entries.

    Keeping the IDs of broken entries stops one bad field from causing a cascade of
    "unknown station" problems elsewhere.
    """
    file = "stations.json"
    stations: dict[str, Station] = {}
    known: set[str] = set()
    for i, entry in enumerate(as_list(raw, file, problems)):
        label = entry_label(entry, i)
        usable = check_fields(file, label, entry,
                              {"id": "str", "name": "str", "lat": "number", "lon": "number"},
                              {"aliases": "list[str]", "closed": "bool", "verified": "bool"},
                              problems)
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            check_duplicate(file, entry["id"], known, problems)
        if not usable or entry["id"] in stations:
            continue
        lat, lon = entry["lat"], entry["lon"]
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            problems.append(f"{file}, entry {label}, field lat/lon: ({lat}, {lon}) "
                            "is outside the NCR box")  # check 9
        stations[entry["id"]] = Station(
            id=entry["id"], name=entry["name"], lat=float(lat), lon=float(lon),
            aliases=tuple(entry.get("aliases", [])), closed=entry.get("closed", False),
            verified=entry.get("verified", True))
    return dict(sorted(stations.items())), known


def parse_lines(raw, problems: list[str]) -> dict[str, Line]:
    """Parse lines.json, including each line's services."""
    file = "lines.json"
    lines: dict[str, Line] = {}
    line_ids: set[str] = set()
    service_ids: set[str] = set()
    for i, entry in enumerate(as_list(raw, file, problems)):
        label = entry_label(entry, i)
        if not check_fields(file, label, entry, {"id": "str", "name": "str", "color": "str",
                                                 "services": "list"}, {}, problems):
            continue
        check_duplicate(file, entry["id"], line_ids, problems)
        services = [parse_service(s, j, entry["id"], service_ids, problems)
                    for j, s in enumerate(entry["services"])]
        services = sorted((s for s in services if s is not None), key=lambda s: s.id)
        lines.setdefault(entry["id"], Line(entry["id"], entry["name"], entry["color"],
                                           tuple(services)))
    return dict(sorted(lines.items()))


def parse_service(entry, index: int, line_id: str, seen: set[str],
                  problems: list[str]) -> Service | None:
    """Parse one service inside a line; None if it is malformed or a duplicate."""
    file = "lines.json"
    label = entry_label(entry, index)
    if not check_fields(file, label, entry, {"id": "str", "stations": "list[str]"},
                        {"loop": "bool"}, problems):
        return None
    if entry["id"] in seen:
        check_duplicate(file, entry["id"], seen, problems)
        return None
    seen.add(entry["id"])
    return Service(entry["id"], line_id, tuple(entry["stations"]), entry.get("loop", False))


def parse_segments(raw, problems: list[str]) -> list[Segment]:
    """Parse segments.json, sorted by ID."""
    file = "segments.json"
    segments: list[Segment] = []
    seen: set[str] = set()
    for i, entry in enumerate(as_list(raw, file, problems)):
        label = entry_label(entry, i)
        if not check_fields(file, label, entry, {"id": "str", "line": "str", "a": "str",
                                                 "b": "str", "time_s": "int"}, {}, problems):
            continue
        if entry["id"] in seen:
            check_duplicate(file, entry["id"], seen, problems)
            continue
        seen.add(entry["id"])
        check_time(file, label, "time_s", entry["time_s"], problems)
        segments.append(Segment(entry["id"], entry["line"], entry["a"], entry["b"],
                                entry["time_s"]))
    return sorted(segments, key=lambda s: s.id)


def parse_transfers(raw, problems: list[str]) -> TransferData:
    """Parse transfers.json: default times, overrides, no-transfer pairs and walkways."""
    file = "transfers.json"
    if not check_fields(file, "(top level)", raw,
                        {"default_other_line_s": "int", "default_same_line_s": "int"},
                        {"overrides": "list", "no_transfer": "list", "walkways": "list"},
                        problems):
        return TransferData(240, 120, (), (), ())
    for name in ("default_other_line_s", "default_same_line_s"):
        check_time(file, "(top level)", name, raw[name], problems)

    overrides = []
    for i, entry in enumerate(raw.get("overrides", [])):
        label = f"override #{i}"
        if check_fields(file, label, entry, {"station": "str", "service_a": "str",
                                             "service_b": "str", "time_s": "int"}, {}, problems):
            check_time(file, label, "time_s", entry["time_s"], problems)
            overrides.append(TransferOverride(entry["station"], entry["service_a"],
                                              entry["service_b"], entry["time_s"]))
    no_transfer = []
    for i, pair in enumerate(raw.get("no_transfer", [])):
        if has_kind(pair, "list[str]") and len(pair) == 2:
            no_transfer.append((pair[0], pair[1]))
        else:
            problems.append(f"{file}, entry no_transfer #{i}: expected two service IDs")
    return TransferData(raw["default_other_line_s"], raw["default_same_line_s"],
                        tuple(overrides), tuple(no_transfer),
                        tuple(parse_walkways(raw.get("walkways", []), problems)))


def parse_walkways(raw: list, problems: list[str]) -> list[Walkway]:
    """Parse the walkways list inside transfers.json, sorted by ID."""
    file = "transfers.json"
    walkways: list[Walkway] = []
    seen: set[str] = set()
    for i, entry in enumerate(raw):
        label = entry_label(entry, i)
        if not check_fields(file, label, entry, {"id": "str", "a": "str", "b": "str",
                                                 "time_s": "int"}, {"one_way": "bool"},
                            problems):
            continue
        if entry["id"] in seen:
            check_duplicate(file, entry["id"], seen, problems)
            continue
        seen.add(entry["id"])
        check_time(file, label, "time_s", entry["time_s"], problems)
        walkways.append(Walkway(entry["id"], entry["a"], entry["b"], entry["time_s"],
                                entry.get("one_way", False)))
    return sorted(walkways, key=lambda w: w.id)
