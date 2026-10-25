# Performance

Two sets of measurements, both on macOS (Apple silicon), Python 3.12, PySide6 6.12, the draft dataset (244 stations, 272 nodes, 582 arcs):

- **18 October 2026**, the first draft (Must and Should tiers). Rows marked *18 Oct* were not measured again.
- **25 October 2026**, after the optional features. Rows marked *25 Oct* were measured again, with `tools/measure_ui.py` and the scripts named below.

Timings use `time.perf_counter` and p95 from `statistics.quantiles` [D18], [D30]. On CI the test budgets are multiplied by 3. Nothing here was measured on Windows or Linux; see "Not measured" below.

| Quantity | Target | Measured | Test | Result |
|---|---|---|---|---|
| Route query p95 (1 000 random pairs, real data) | ≤ 50 ms | 0.25 ms (*18 Oct*) | T29 | met; the test still passes |
| Alternative routes p95 (300 random pairs, up to 3 routes each) | ≤ 50 ms | 4.4 and 4.7 ms for two seeds; median 2 ms, worst 8.6 ms (*25 Oct*) | `tests/test_alternatives.py` | met |
| Search per keystroke p95 (all prefixes of all names + 200 typos) | ≤ 50 ms | 2.7 ms, 3 521 queries (*18 Oct*) | T29 | met |
| Data load + validation | ≤ 1 s | ≈ 3 ms (*18 Oct*) | T29 | met |
| Window visible after launch (imports included) | ≤ 2 s | 0.50–0.53 s, 3 runs (*25 Oct*); the very first, cold run was 2.7 s (*18 Oct*) | manual, `startup` script | met when warm |
| Steady-state memory, route shown | ≤ 150 MB | **162–200 MB**, 5 runs on the real window system (*25 Oct*) | `tools/measure_ui.py`, `ps -o rss` | **not met on macOS**, see below |
| Route p95 on the synthetic 10× network (2 634 stations) | ≤ 100 ms | 3.3 ms (*18 Oct*) | T30 | met |
| Drawing one frame of the map | median ≤ 16.7 ms | median 3.0–10.2 ms, p95 ≤ 11.6 ms (*25 Oct*) | `tools/measure_ui.py` | met on this machine |
| One zoom step, including the label overlap test | — | 0.2–0.3 ms (*25 Oct*) | `tools/measure_ui.py` | informational |
| All-pairs oracle (59 000 ordered pairs vs networkx) | — | ≈ 9 s (*18 Oct*); the whole suite with it takes 59 s (*25 Oct*) | T19 (slow) | passes |

## Frame time

"Frame time" here is the time `viewport().grab()` takes to paint the map once. That is the Qt painting work for a frame, without the desktop's own compositing, so it is a stand-in for the real frame time and not the same thing. Median over 100 repaints, with a 79-minute route on screen:

| View | Real window system (cocoa) | `offscreen` |
|---|---|---|
| fitted to the route | 3.0 ms (p95 4.7) | 1.4 ms (p95 2.4) |
| whole network (includes the fit itself) | 10.2 ms (p95 11.6) | 3.3 ms (p95 3.9) |
| zoomed in 4× with labels | 9.7 ms (p95 11.4) | 2.8 ms (p95 3.2) |
| one animation tick and a frame | 9.8 ms (p95 11.2) | 2.8 ms (p95 3.2) |

The 60 frames per second budget is 16.7 ms, so all of these fit on this machine. The whole-network view is the slowest (about 10 ms), so it is the one to check first on a slower computer.

## Memory

The target is ≤ 150 MB resident after start-up. Resident memory was measured with `ps -o rss` on the real macOS window system, because a window on the `offscreen` platform uses much less (about 100 MB for the same planner window) and is not comparable.

Run-to-run spread is large, about ±30 MB for the same program, so one run proves little. Four runs each, same steps (empty widget, planner window, then a route):

| | empty `QWidget` 1280 × 800 | planner window | route shown |
|---|---|---|---|
| before the optional features (commit `273c665`) | 109, 125, 122, 134 MB | 121, 149, 182, 181 MB | 137, 165, 194, 197 MB |
| after (`HEAD`, this document) | 127, 126, 124, 127 MB | 180, 185, 180, 181 MB | 177, 192, 200, 200 MB |

The ranges overlap. The optional features may have added some memory, but the spread is too wide to show it, and both versions are above 150 MB on macOS. A bare `QWidget` already takes 109–134 MB here, so most of the target is spent on Qt itself. The 18 October figure of ≈ 174 MB is close to both.

The team still has to decide whether to keep the 150 MB target, record a decision to change it, or measure on Windows and Linux first. Those systems may well give a different answer, and nothing in this repository says they do.

## Not measured

- **Windows and Linux**: memory and frame time. On Windows read the memory in Task Manager (Details tab, "Memory (active private working set)"); `python tools/measure_ui.py` prints the frame times anywhere and the memory on macOS and Linux.
- **A very slow computer**, a 4K screen, or several monitors.

## Test coverage

`pytest --cov=metro` (all 390 tests, including the slow oracle), 25 October 2026:

| Scope | Line coverage |
|---|---|
| Core (`metro/` excluding `ui/`) | 97% (target ≥ 80%) |
| `metro/ui/` | 97% |
| Whole package | 97% (2 434 statements, 65 not run) |

`RouteWorker.compute` shows as uncovered only because coverage does not trace code running on a `QThread`; T25–T27 exercise it.

## Reproduce

```bash
pytest --cov=metro --cov-report=term-missing   # coverage and the timing tests
python tools/measure_ui.py                      # frame time, and memory on macOS and Linux
QT_QPA_PLATFORM=offscreen python tools/measure_ui.py   # the same without opening a window
```
