# Design decisions

Decisions made after A3. A3 says "no design change is silent", so every change from the A3 design is recorded here with its reason.

## Simplifications versus A3

| ID | A3 said | We build | Why |
|---|---|---|---|
| D26 | Trie with cached top-8 per node (A2 Alg. 5, [D6]) | Linear scan over all names, with the same ranking rules | About 300 stations × about 20 characters is under 1 ms per keystroke. A trie adds code without a measurable gain. |
| D27 | Custom viewport maths and a spatial grid (A2 Alg. 6) | Qt's built-in `AnchorUnderMouse` zoom, scale clamping, and `view.items(rect)` for hit-testing | Qt already implements zoom-about-cursor and spatial indexing (BSP tree). Reimplementing them adds risk. |
| D28 | Three oracles (own Floyd–Warshall, networkx, Dijkstra) and two-tier CI [D15] | Floyd–Warshall on the toy fixtures; networkx all-pairs on the real data, as a single test marked `slow` | Two independent oracles are still independent of our router, and the full all-pairs check runs in tens of seconds. |
| D29 | Hypothesis property tests on generated networks | Seeded-random tests on the real network and the toy fixtures; Hypothesis is optional (Could) | Fewer tools to explain. Determinism is easier to demonstrate. |
| D30 | `pytest-benchmark`, mypy strict, import-linter | Plain `time.perf_counter` tests, type hints (mypy non-strict, optional), and one import-check test | Same guarantees with tools that need no explanation. |
| D31 | `RouteFinder` Protocol (Strategy) injected from `main.py` | A plain function `find_route(graph, network, src, dst, criterion)`; the criterion selects a key function | Swapping the algorithm still touches only `router.py`. The UI only ever sees the `Route` dataclass. |
| D32 | Executor abstraction (`InlineExecutor` / `QThreadExecutor`) | One `RouteWorker` on one `QThread`; core tests call `find_route` directly | Only one executor exists in the real app, so the abstraction served tests only. |
| D33 | Full FSM with every (phase, action) pair | An `AppState` dataclass whose `phase` is derived from its fields, plus a few pure update functions | Illegal states become unrepresentable without a transition table. |
| D34 | Yen's k-shortest alternatives (FR17) | Built after the feature freeze as arc masking, not Yen's: see [D47] | Scope tier [D24]; Yen's paths differ by one station, which is no use to a rider. |
| D35 | TOML settings file | No settings file of our own; theme and favourites use QSettings, see [D55] | Nothing needs configuration in the Must tier; the optional features need two remembered values. |

## Kept from A3 exactly

The line-expanded routing graph; lexicographic Dijkstra with a super-source and early exit; WALK legs [D17]; the fuzzy threshold [D16]; validation that reports all problems at once; the worker thread with a stale-result token and a 2 s watchdog; inline (non-modal) errors [D19]; the accessibility baseline [D20]; label level-of-detail [D21]; golden routes that check structure only [D22]; the toy fixtures with their exact expected numbers.

## Later decisions

### D36 — Cross-file checks in their own module (Step 2)

The PRD layout puts all validation in `data.py`. With all eleven checks, that file would pass the 300-line limit, so the checks that need more than one file (4, 6, 7, 8, 10, 11) live in `metro/validate.py`. `data.py` still owns reading, per-entry field checks (2, 3, 5, 9) and building the `Network`. `load_network` is still the only entry point.

### D37 — Broken fixtures store only the changed file (Step 2)

Each folder in `tests/fixtures/broken/` holds only the file(s) that differ from `toy_metro`. The `broken_dataset` test fixture copies `toy_metro` to a temporary folder and lays the broken files over it. This keeps each defect visible in a single small file instead of 4 near-identical copies.

### D38 — Search details (Step 5)

- **Index entries carry the name and the closed flag.** PRD §5.4 describes index entries as `(text, station_id, is_code)`. Each `IndexEntry` also stores the canonical name (for the `(rank, distance, name)` sort) and `closed` (so results can be dimmed) to avoid a second lookup per result.
- **Fuzzy also compares with the start of the name.** Comparing a 5-letter query with a 11-letter name always fails the length check, so a typo while still typing ("rajib") would never be found. `classify` compares the query with the whole name *and* with the name's first `len(query)` characters, using the same `k` [D16].
- **Codes match only exactly.** A code is short and arbitrary, so prefix or fuzzy matches on codes would mostly be noise.
- **Whitespace becomes a space before control characters are dropped.** Tabs and newlines are Unicode category `Cc`; dropping them first would join words ("rajivchowk"). Found by `test_t13_normalise_steps`.

### D39 — Route text shared by the CLI and the UI (Step 6)

`metro/describe.py` turns a `Route` into the summary line, leg rows and interchange rows of §6.4. The CLI (`tools/route_cli.py`) and the route panel both use it, so the wording and the minute rounding live in one place. It is pure Python, so it sits in the core.

### D40 — Real-data router tests in their own file (Step 6)

T1–T10 and T20 run on the real data and are in `tests/test_router_real.py`; `tests/test_router.py` keeps the toy-fixture tests. One file for both would pass the 300-line limit.

### D41 — T2 uses a large override, not 104 s (Step 6)

A3 says the Janakpuri West transfer is "overridden to 104 s". A transfer *cheaper* than normal cannot force a Blue-only route, so this looks like a typo. T2 sets the Janakpuri West `BLUE-MAIN`↔`MAG-1` transfer to 10 000 s and asserts that Uttam Nagar East → Botanical Garden is a single Blue leg with 0 interchanges.

### D42 — How the draft dataset was produced (Step 6)

The real data was drafted from the DMRC GTFS feed plus Wikipedia/OpenStreetMap for the 2025–26 sections (details and every source in `data/README.md`). The drafted CSVs in `data/source/` are now the team's master copy, and `tools/csv_to_json.py` generates the JSON. Every station is `verified: false` until the team checks it. The 30 golden routes in `tests/golden/routes.json` are structures expected from the DMRC map (`"checked": false` until the team confirms each one).

### D43 — Request bookkeeping lives in `RouteRunner` (Step 8)

PRD §6.5 describes the request number, cancel event, 150 ms timer and 2 s watchdog as part of the main window. They are in `RouteRunner` (`metro/ui/worker.py`) instead, next to `RouteWorker`. The main window calls `runner.start(...)` / `runner.cancel()` and listens to `found`, `failed` and `slow`. All the threading code is then in one file, and the window only deals with `AppState`. After a watchdog timeout the request number is also increased, so a late result of the abandoned search is treated as stale.

### D44 — Esc is handled in `MainWindow.keyPressEvent` (Step 8)

A window-wide `QShortcut` for Esc did not fire while a text field had focus. Key presses that no child widget uses bubble up to the window, so `keyPressEvent` sees Esc from anywhere. The search box consumes Esc while its list is open, so "Esc closes the list first, then resets" needs no extra check.

### D45 — Suggestions are an inline list, not a popup (Step 8)

The suggestion list is a `QListWidget` placed directly under each field (as in the §6.1 layout), not a floating popup. The keyboard focus stays in the field; an event filter maps Up/Down/Enter/Esc onto the list. This avoids popup focus problems and is simple to test.

### D46 — A station typed over is no longer chosen (Step 8)

Editing the text of a field after choosing a station clears that choice (`SearchBox.cleared`). Otherwise the field could show one name while the state held another station.

## Optional features (Could tier, built after the M4 feature freeze, 25 October 2026)

These were requested explicitly after the Must and Should tiers were done; each keeps the rules in PRD §0.1 (no Qt in the core, files about 300 lines or fewer, accessible names on every control).

### D47 — Alternative routes by masking arcs (FR17)

`metro/alternatives.py` returns up to 3 routes: the best route for the chosen criterion first, then the best route of each other criterion, then "masked" routes. A masked route is `find_route` run on a copy of the graph with some arcs removed: every transfer and walk arc at a change station of a route already found, or the middle hop of each ride. It repeats once on what it finds, keeps routes up to 1.5 times as slow as the fastest, and sorts by the chosen criterion with the leg stations as tie-break, so the result is the same every time. `router.py` is untouched and the file imports no Qt.

Yen's algorithm (the A2 idea, [D34]) gives paths that differ by one station on the same line. That is a poor "alternative" for a rider; masking a change station or a stretch of line gives a different way to travel. It runs on the UI thread, not the worker: p95 over 300 random pairs is about 4.5 ms on the development Mac, and `tests/test_alternatives.py` checks it against the 50 ms budget. If it ever fails, the window logs the error and still shows the route.

### D48 — Favourite routes

A favourite is (source, destination, criterion). The list logic is in `metro/favorites.py` (no Qt): add or remove at the front, at most 20, and `decode` that never raises, so a damaged or outdated saved value gives an empty list and entries naming stations that no longer exist are dropped. The route itself is not saved; choosing a favourite fills the fields and the Criterion box and searches again, so it follows data changes and closures (a closed station gives the ER6 message). `FavoritesBar` keeps the list in QSettings.

### D49 — Changing the criterion searches again at once

Before, choosing a different criterion left a route on screen that no longer matched the box until Find was pressed. Now `on_criterion` stores the criterion and calls `find()`, which does nothing unless both stations are valid. `set_criterion` stays a pure state update.

### D50 — Overlapping labels are hidden, not just zoom-tiered

[D21] picks which labels may show at each zoom, but at tier 2 neighbouring stations still print over each other. `map_labels.declutter` tries labels from the most to the least important (interchange, terminal, rest; station ID as tie-break) and keeps one only if its padded rectangle does not overlap one already kept, with a 64 px grid so it stays fast. Overlap depends only on distances between labels, so panning cannot change the result and it is recomputed on zoom only (about 0.2 ms per zoom step measured).

### D51 — Visible zoom, fit, theme and play buttons on the map

Scrolling and the `+ - 0` keys are invisible. `MapControls` floats buttons in the top-right of the map. They take keyboard focus by Tab but not by click, so the map keeps its key shortcuts. The keys still work.

### D52 — Route stations and changes drawn on top of the dimmed network

Dimming the network to 25% made the route's own stations hard to read. The route's markers and names go back to full opacity, every station on it gets a small disc, and each change gets a heavy ring and a boxed label ("⇄ Change at X" or "⇄ Walk X → Y"). Labels of neighbouring changes alternate above and below the ring so they rarely collide.

### D53 — Station lists are extra rows, not a tree

A ride with stations in between gets a "▶ N stations in between" row in the existing `QListWidget`; opening it inserts one row per station. A `QTreeWidget` would have changed the row model that tests, the accessibility check and leg focusing rely on. Enter and Space are handled in an event filter, because `itemActivated` also fires on a single click on some platforms and a row would toggle twice. The row has a spoken description ("Show 8 stations in between") because the arrow glyph is read out as "black right-pointing triangle". `test_full_workflow_shows_route` now expects the extra row.

### D54 — Station card on right-click and Ctrl+I, not on left-click

FR4 says a click fills From, then To, so a left-click cannot also open a card. Right-click opens a menu (Details, Set as From, Set as To; a submenu per station where markers overlap) and Ctrl+I opens the card of the To station, else the From station, for keyboard users. The card is not modal. Each line is a coloured tag that also says the line's name, with black or white text picked by contrast ratio ([D20]).

### D55 — Themes, and settings kept as an .ini file

A `Theme` is plain data: map colours and a style sheet. The dark sheet restyles every widget; the light sheet only styles the banner, field hints and map buttons and leaves the platform look alone. The map recolours in place, redraws the route (with a soft glow in dark) and keeps the camera and dimming. The first choice is light; the OS setting is not read.

Settings are saved by `app_settings()` as an .ini file. `QSettings(org, app)` ignored `setDefaultFormat` on macOS and wrote a plist, which meant the tests would have overwritten the developer's real saved theme; an explicit `IniFormat` can be redirected with `QSettings.setPath`, and `tests/conftest.py` does that for every test. `tests/test_theme.py` checks that the file really lands in the test's temporary folder.

### D56 — Route tabs with a caption, and a comparison table

The route panel shows "Route 1/2/3" tabs and, under them, "Best at: Fastest, Fewest interchanges" for the selected route. Putting the badge in the tab text gave "Rout…" on a 380 px panel, so the tab only carries the number (tooltips carry the full summary). `RouteCompareDialog` shows one column per route; a value is bold when the route has that criterion's badge, using the same `route_badges` as the caption, so the two cannot disagree when two routes tie to the minute but not to the second. "Choose this route" calls `AppState.choose_alternative`.

### D57 — Export never raises

`export_route` copies to the clipboard or saves UTF-8 text or Markdown (every intermediate station listed). A file problem becomes a message in the banner and the route stays; the file name is made safe for Windows ('Rajiv-Chowk-to-Hauz-Khas.txt') and a missing extension is added. Found by test: "Haat - INA" first became "Haat---INA".

### D58 — Route animation

`RouteAnimator` moves a marker along the route's polyline at 250 ms per station (3 to 15 s). The geometry is plain functions and the timer only calls `advance(ms)`, so tests are exact and do not wait. Step jumps to the next or previous station and pauses; Space plays or pauses; after the end, Play starts again from the beginning. The marker is outside `network_items` and `overlay.items`, so dimming, clearing and the theme redraw leave it alone.

### D59 — Splitting the window to keep to 300 lines

`main_window.py` reached 344 lines. The left column became `SidePanel` (widgets and layout, no logic), the handlers for the optional features became `ExtrasMixin` in `extras.py` (same method names, so nothing that calls them changed), and the map's network drawing, label logic and station menu became `network_items.py`, `map_labels.py` and `station_menu.py`. `ExtrasMixin` depends on the window's attributes and is not usable alone, which is the price of keeping one `MainWindow` class.
