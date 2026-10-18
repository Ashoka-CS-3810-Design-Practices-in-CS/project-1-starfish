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
| D34 | Yen's k-shortest alternatives (FR17) | Not planned (Could tier, only if all else is done) | Scope tier [D24]. |
| D35 | TOML settings file | Not built unless the Options dialog [O] is built | Nothing needs configuration in the Must tier. |

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
