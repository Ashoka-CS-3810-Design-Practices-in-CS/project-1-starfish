# Viva notes

Running notes for the viva, one section per build step.

## Step 1 — Skeleton, CI, architecture test (M1)

**What was built.** `pyproject.toml` (runtime dependency: PySide6 only; test extras: pytest, pytest-qt, networkx, ruff, pytest-cov), the empty `metro/` and `metro/ui/` packages, a GitHub Actions workflow that lints and tests on Ubuntu, Windows and macOS, and `tests/test_imports.py`.

**Key functions.**
- `core_files()` (`tests/test_imports.py`): lists every `.py` file under `metro/` except those in `metro/ui/`.
- `test_core_never_imports_pyside6()`: reads each core file as text and fails if it contains `import PySide6` or `from PySide6`.
- `test_core_files_exist()`: makes sure the check is not passing just because no files were found.

**Likely questions.**
- *Why check imports with a text search instead of a tool like import-linter?* — It is ten lines, needs no extra tool, and gives the same guarantee for our one rule ([D30]).
- *Why keep Qt out of the core at all?* — The core can then be tested without a display, and the routing logic can be reused by the CLI (`tools/route_cli.py`) unchanged.
- *Why does the slow test only run on Ubuntu?* — It checks all station pairs and is OS-independent pure Python; running it once is enough.

## Step 2 — Data model, loading and validation (M2)

**What was built.** The frozen dataclasses in `metro/models.py`, three exception classes in `metro/errors.py`, the loader in `metro/data.py`, the cross-file checks in `metro/validate.py`, the two toy fixtures, and one-defect fixtures under `tests/fixtures/broken/`.

**Key functions.**
- `load_network(folder)`: reads the four JSON files, runs every check, and either raises `DataError` with *all* problems or returns a `Network` whose collections are sorted by ID.
- `read_json(path)`: turns a missing file or bad JSON into `DatasetUnreadable` (ER8), so the start-up dialog can name the file.
- `check_fields(...)`: the one generic check for "required field missing or wrong type". `has_kind` handles the Python quirk that `True` is an `int`.
- `check_segment_coverage(...)`: matches service hops to segments by `(line, {a, b})`; any hop without a segment, or segment without a hop, is a problem.
- `is_connected(network)`: breadth-first search over stations; disconnection is only a warning (UC5).

**Likely questions.**
- *Why collect problems in a list instead of raising on the first one?* — A maintainer fixing a dataset would otherwise need one run per mistake. One run shows everything (ER9).
- *Why do you keep IDs of broken station entries?* — If station `I` has a bad `lat`, it still exists. Forgetting it would cause extra "unknown station I" problems elsewhere, which would hide the real one.
- *Why sort everything by ID?* — So that the order of records in the files cannot change the graph, node numbers or tie-breaks. Shuffled files must give identical routes (T10, [D4]).

## Step 3 — Routing graph (M2)

**What was built.** `metro/graph.py`: the line-expanded routing graph, plus tests for the exact node and arc counts of both toy fixtures (TM0, TL0), closures, overrides, `no_transfer`, one-way walkways and determinism.

**Key functions.**
- `build_graph(network)`: makes one node per (open station, service) pair, numbered in sorted order, then adds the three kinds of arcs and sorts each adjacency list.
- `add_ride_arcs(...)`: for each hop of each service (including a loop's closing hop), adds a `ride` arc both ways with the segment's time. Hops touching a closed station are skipped, which cuts the service.
- `add_transfer_arcs(...)`: at each station, adds a `transfer` arc between every ordered pair of services, except pairs in `no_transfer`. A station with k services gets k(k−1) arcs.
- `transfer_time(...)`: override if one exists for that station and pair, otherwise 120 s for a branch change on the same line and 240 s for a different line.
- `add_walk_arcs(...)`: joins every node of one station to every node of the other, both ways unless `one_way`.

**Likely questions.**
- *Why not one node per station?* — Then "arrive on Red, leave on Blue" and "stay on Red" would look the same, and the transfer cost could not be charged. Splitting a station by service makes the change a real arc.
- *Why an adjacency list rather than a matrix?* — Roughly 1 000 arcs versus about 120 000 cells for a matrix of ~350 nodes; Dijkstra only ever needs "the arcs leaving this node".
- *What does closing a station do?* — It gets no nodes, so no ride arc can pass through it ([D1]); the test `test_closed_station_has_no_node` shows C closed leaves Red split into A–B and D.
