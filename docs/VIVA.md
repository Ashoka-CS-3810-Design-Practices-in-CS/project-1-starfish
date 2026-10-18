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

## Step 4 — Route search and assembly (M3)

**What was built.** `metro/router.py` (lexicographic Dijkstra, route assembly, direction labels, display minutes) and `tests/oracle.py` (Floyd–Warshall). Tests cover TM1–TM11 and TL1–TL5 with exact numbers, and Dijkstra agrees with Floyd–Warshall on every ordered pair of both toy fixtures. TM12 (A→A) is about `can_find`, so it is tested with `app_state.py` in Step 8.

**Key functions.**
- `find_route(graph, network, src, dst, criterion, cancel)`: pushes every node of `src` at cost (0, 0, 0) (the super-source), pops the cheapest key, skips stale heap entries (lazy deletion), and stops at the first popped node whose station is `dst` (early exit). Returns `None` when the heap empties.
- `arc_cost(time_s, kind)`: a ride adds (t, 0, 1); a transfer or walk adds (t, 1, 0). The criterion's key function only reorders this tuple, and Python compares tuples left to right, so tie-breaks come for free.
- `assemble_route(...)`: splits the path into pieces (`split_into_pieces`), turns ride pieces into RIDE legs, whatever lies between two rides into one `Interchange`, and walks before the first or after the last ride into WALK legs. It then asserts the three invariants.
- `direction_label(...)`: "towards <terminus>" for normal services; for a loop, the next interchange station in the travel direction.
- `all_pairs_times(graph)` (`tests/oracle.py`): Floyd–Warshall on node times, taking the minimum over all nodes of each station.

**Likely questions.**
- *Why does early exit guarantee no false change at the destination?* — We stop the moment *any* node of the destination station is popped. A transfer arc at the destination would only make a more expensive node of the same station, which is never popped first.
- *Why is lexicographic Dijkstra still correct?* — All arc costs are non-negative tuples, and adding a non-negative tuple never makes a tuple lexicographically smaller. That is the only property Dijkstra needs.
- *Why is a walk at the start not an interchange?* — You have not boarded anything yet, so nothing is being "changed" ([D17]). It is still counted as a change in the search key, so the reported count can only be smaller than the key's (T21).
- *How are ties broken?* — Heap entries are `(key, node)`, so equal keys fall back to the node index, which comes from sorted IDs. TL5 checks that the loop direction is the same on every run.

## Step 5 — Station search (M3)

**What was built.** `metro/search.py`: normalisation, the search index, the A2 ranking rules as a linear scan [D26], and a banded Levenshtein. Tests cover T11–T14, the fuzzy threshold [D16], and 10 000 random hostile strings. Measured p95 is about 4 ms per keystroke on a 300-station index (target ≤ 50 ms).

**Key functions.**
- `normalise(text)`: cut to 100 characters, NFKC (turns full-width "ＲＡＪ" into "RAJ"), whitespace to spaces, drop control characters, lowercase, collapse spaces, "sec" → "sector".
- `build_index(stations)`: one entry per code, name and alias, all normalised once at start-up.
- `classify(query, entry, k)`: decides CODE / NAME / PREFIX / SUBSTRING / FUZZY for one entry, trying the cheap checks first.
- `levenshtein_within(a, b, k)`: two-row edit distance that gives up as soon as every value in a row is above k.
- `search(index, query)`: keeps each station's best match and returns the top 8 by `(rank, distance, name)`.

**Likely questions.**
- *Why is stopping early correct?* — Each cell in the next row is at least the smallest value in the current row (all three moves add 0 or 1 to a cell from the row above or the same row). If the whole row is above k, the final answer must be too.
- *Why no fuzzy matching below 3 characters?* — With 1–2 letters, one edit can turn the query into almost anything, so every station would match ([D16]).
- *Why not a trie?* — About 300 stations × 3 texts is ~1 000 comparisons per keystroke, a few milliseconds. A trie would need insertion, traversal and cached top-8 code to save time nobody can notice ([D26]).

## Step 6 — Real data, CLI and real-data tests (M3)

**What was built.** The draft dataset (244 stations, 13 services on 9 lines, 260 segments; see `data/README.md`), `tools/csv_to_json.py` (team CSV → JSON), `tools/route_cli.py` (the walking skeleton), `metro/describe.py` (route text), 30 golden routes, and tests T1–T10, T19 (networkx, slow), T20, T29 and T30.

**Key functions.**
- `convert_lines_and_segments(...)` (`tools/csv_to_json.py`): groups CSV rows by service, sorts by `seq`, makes one segment per (line, station pair), and drops the repeated first station of a loop after using its time for the closing segment.
- `route_cli.main(argv)`: loads, validates, picks stations through `search` (only exact CODE/NAME matches are routed; otherwise it prints "Did you mean"), routes, and prints `route_lines`.
- `route_lines(network, route)`: summary line, numbered legs, with an "⇒ Change at …" row between consecutive RIDE legs.
- `networkx_times(graph, src)` (`tests/test_oracle_real.py`): an independent oracle with a super-source and one super-sink per station.
- `synthetic_network()` (`tests/test_performance.py`): 9 × 330 stations with every 8th station shared, giving about 2 600 stations and 12% interchanges.

**Measured.** Route p95 0.25 ms on real data (target 50 ms); 3.3 ms on the synthetic network (target 100 ms); load + validate about 3 ms (target 1 s). All 59 000 ordered pairs agree with networkx.

**Likely questions.**
- *Where did the data come from and how much is verified?* — DMRC's GTFS feed for order, coordinates and running times; Wikipedia and OpenStreetMap for the sections opened in 2025–26; 120 s default where no times exist. Nothing is marked verified until the team checks it (`data/README.md`).
- *How can the golden test not be circular?* — The golden file holds structures expected from the official map (line sequence and interchange stations), not router output. Minutes are compared to networkx, not written down.
- *What does T20 prove?* — Closing a station only removes nodes and arcs, so it can never create a shorter path. If a closure ever made a route faster, the graph build or the search would be wrong.

## Step 7 — Map view (M4)

**What was built.** `metro/ui/map_view.py` (the `MapView` widget) and `metro/ui/route_overlay.py` (route drawing and selection rings), plus `station_lines` and `station_tooltip` in `metro/describe.py`. Tests T22–T24 and checks for clicks, the overlay and label level-of-detail are in `tests/test_gui_map.py`.

**Key functions.**
- `project(lat, lon, origin)`: x = (lon − lon0)·cos(lat0)·K, y = −(lat − lat0)·K. The cosine stops east–west distances from being stretched; the minus sign puts north at the top because screen y grows downwards.
- `MapView.zoom_by(factor)`: works out the target zoom, clamps it to 0.2–20 × the fit scale, and scales by the ratio. Qt's `AnchorUnderMouse` keeps the point under the cursor fixed [D27].
- `MapView.stations_near(pos)`: asks Qt for the items in a 16 × 16 px square (`items(QRect)`, backed by Qt's BSP index), keeps station markers, and sorts them by pixel distance.
- `MapView.update_labels()`: computes the label tier from the zoom and only touches labels when the tier changes [D21].
- `RouteOverlay.draw(route, network)`: draws each leg as thick lines on top; every second ride gets a white dashed centre line so neighbouring legs differ without colour; walks are dotted grey. The network is never rebuilt.

**Likely questions.**
- *Why do markers and labels keep their size when zooming?* — `ItemIgnoresTransformations` draws them in pixels, and pens are cosmetic, so line width is in pixels too. Only positions follow the zoom.
- *How do you tell a click from a drag?* — The press position is remembered; a release within 4 px of it counts as a click. Anything further was a pan.
- *What happens with a 0 × 0 window?* — `fit_rect` and `fit_all` return early (ER11); T23 resizes to 0 × 0 and checks the transform is unchanged.

## Step 8 — App state, search boxes, route panel, worker, main window (M4, feature freeze)

**What was built.** `metro/app_state.py` (pure state + update functions), `metro/ui/search_box.py`, `metro/ui/route_panel.py` (route rows and the banner), `metro/ui/worker.py` (`RouteWorker` on a `QThread` + `RouteRunner`), `metro/ui/main_window.py` and `main.py`. Tests: T15, T16, TM12 (`tests/test_app_state.py`) and T25–T28 plus the other workflows (`tests/test_gui.py`).

**Key functions.**
- `AppState.phase`: worked out from the fields (computing → "Computing", a route → "RouteShown", …). There is no stored phase that could disagree with the data [D33].
- `select_station(state, network, field, station_id)`: refuses closed stations (ER6), flags same-station (ER5), and clears the old route because a new choice is the user's own action.
- `can_find(state, network)`: the single place that decides whether Find is allowed; its reason becomes the disabled button's tooltip.
- `RouteRunner.start / cancel / is_current`: each request gets a number; starting a new one or resetting increases the number and sets the old cancel event, so an old result is recognised as stale and dropped (ER14). Timers give "Computing…" after 150 ms and fail the request after 2 s (ER13).
- `MainWindow.apply(state)`: the only function that changes widgets. Every handler computes a new `AppState` and calls `apply`.

**Likely questions.**
- *How do you keep the UI responsive?* — `find_route` runs in `RouteWorker.compute` on a separate `QThread`. The request signal is queued across threads, and results come back as signals to the UI thread.
- *What stops an old, slow result from overwriting a newer one?* — The request number. `is_current` compares the result's number with the latest; anything else is discarded. T25 tests this with a deliberately slow search function.
- *Why can't the cancel just kill the thread?* — Killing a thread can leave data half-updated. Instead `find_route` checks the cancel event every 256 pops and stops cleanly by raising `RouteCancelled`.
- *What happens on an unexpected exception?* — The worker logs the stack trace to `metro.log` and the user sees "Something went wrong. Your selection was kept." with Retry (ER17).

## Step 9 — Messages, start-up dialog, accessibility, criteria, packaging (M5)

**What was built.** All A3 Table 12 messages are in place (inline banner and field hints; the start-up dialog is the only modal one). Tests for T21 (the Should-tier criteria), the accessibility baseline, the criterion workflow and the start-up dialog text. `packaging/metro.spec` builds a one-folder desktop app with PyInstaller (checked on macOS).

**Key functions.**
- `main.problems_text(error, folder)`: "The network data has N problems." + the first 10 + the data folder (ER8–ER10).
- `main.show_data_error(...)`: the modal dialog with Open folder / Quit; `main()` then returns exit code 1 without creating the main window.
- `fewest_changes_key` / `fewest_stops_key` (`metro/router.py`): each criterion is one key function that reorders the (time, changes, stops) tuple — nothing else in the router changes.
- `test_accessibility_baseline`: walks every button, field, combo box and list in the window and fails if any has no accessible name.

**Likely questions.**
- *Why is fewest-changes allowed to report fewer interchanges than its key counts?* — A walk at the start or end counts as a change in the key (so the search avoids pointless walks) but is shown as a WALK leg, not an interchange [D17]. T21 checks `reported ≤ key`.
- *Why is only the start-up error modal?* — Without data there is nothing to show, so the user must decide (open the folder or quit). Every other error leaves the app usable, so it is shown inline and never blocks [D19].
- *How is colour never the only cue?* — Leg rows show the line name next to the swatch, and neighbouring legs on the map differ by a dashed centre line; walks are dotted.

**Still to do by the team:** the manual smoke test on Windows, macOS and Linux (A3 M5).
