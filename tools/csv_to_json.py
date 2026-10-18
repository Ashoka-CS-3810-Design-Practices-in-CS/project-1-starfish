"""Convert the team-maintained CSV files in data/source/ into the JSON files the app loads.

Usage: python tools/csv_to_json.py data/source data

Reads stations.csv, lines.csv and services.csv; writes stations.json, lines.json and
segments.json. transfers.json is small and edited by hand, so it is not generated.
For a loop service, the last CSV row repeats the first station and carries the time of the
closing hop (last station -> first station).
"""

import csv
import json
import sys
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    """All rows of a CSV file as dictionaries keyed by the header."""
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def convert_stations(rows: list[dict[str, str]]) -> list[dict]:
    """stations.csv rows -> stations.json records (aliases are separated by ';')."""
    return [{"id": r["id"], "name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]),
             "aliases": [a for a in r["aliases"].split(";") if a],
             "closed": r["closed"] == "true", "verified": r["verified"] == "true"}
            for r in rows]


def convert_lines_and_segments(line_rows: list[dict[str, str]],
                               service_rows: list[dict[str, str]]) -> tuple[list, list]:
    """lines.csv + services.csv -> (lines.json records, segments.json records)."""
    lines = {r["line_id"]: {"id": r["line_id"], "name": r["name"], "color": r["color"],
                            "services": []} for r in line_rows}
    segments: dict[tuple[str, frozenset], dict] = {}
    by_service: dict[str, list[dict[str, str]]] = {}
    for r in service_rows:
        by_service.setdefault(r["service_id"], []).append(r)
    for service_id, rows in by_service.items():
        rows.sort(key=lambda r: int(r["seq"]))
        loop = rows[0]["loop"] == "true"
        stations = [r["station_id"] for r in rows]
        for prev, row in zip(rows, rows[1:]):
            key = (row["line_id"], frozenset((prev["station_id"], row["station_id"])))
            segments.setdefault(key, {"line": row["line_id"], "a": prev["station_id"],
                                      "b": row["station_id"],
                                      "time_s": int(row["time_from_prev_s"])})
        if loop:
            stations = stations[:-1]  # the repeated first station only carried the closing time
        lines[rows[0]["line_id"]]["services"].append(
            {"id": service_id, "stations": stations, "loop": loop})
    numbered = [{"id": f"S-{i:04}", **seg} for i, seg in enumerate(segments.values(), start=1)]
    return list(lines.values()), numbered


def write_json(path: Path, records) -> None:
    """Write records as indented UTF-8 JSON with a trailing newline."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=1, ensure_ascii=False)
        f.write("\n")


def main(source: Path, target: Path) -> None:
    """Convert every CSV in `source` and write the JSON files into `target`."""
    write_json(target / "stations.json", convert_stations(read_csv(source / "stations.csv")))
    lines, segments = convert_lines_and_segments(read_csv(source / "lines.csv"),
                                                 read_csv(source / "services.csv"))
    write_json(target / "lines.json", lines)
    write_json(target / "segments.json", segments)
    print(f"wrote {len(lines)} lines and {len(segments)} segments to {target}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python tools/csv_to_json.py <source-folder> <data-folder>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
