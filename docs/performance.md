# Performance

Measured on 18 October 2026, macOS (Apple silicon), Python 3.12, PySide6 6.12, on the draft dataset (244 stations, 272 nodes, 582 arcs). Timings use `time.perf_counter` and p95 from `statistics.quantiles` [D18], [D30]. On CI the test budgets are multiplied by 3.

| Quantity | Target | Measured | Test | Result |
|---|---|---|---|---|
| Route query p95 (1 000 random pairs, real data) | ≤ 50 ms | 0.25 ms | T29 | met |
| Search per keystroke p95 (all prefixes of all names + 200 typos) | ≤ 50 ms | 2.7 ms (3 521 queries) | T29 | met |
| Data load + validation | ≤ 1 s | ≈ 3 ms | T29 | met |
| Window visible after launch (imports included) | ≤ 2 s | 0.5–0.8 s warm; 2.7 s on the very first, cold run | manual | met when warm |
| Steady-state memory | ≤ 150 MB | ≈ 174 MB | manual (`ps -o rss`) | **not met on macOS** — see below |
| Route p95 on the synthetic 10× network (2 634 stations) | ≤ 100 ms | 3.3 ms | T30 | met |
| Zoom/pan frame time | median ≤ 16.7 ms | not measured | informational | — |
| All-pairs oracle (59 000 ordered pairs vs networkx) | — | ≈ 9 s | T19 (slow) | passes |

## Memory

On the same machine a bare PySide6 window (an empty `QWidget`, 1280 × 800) already uses about 118 MB resident, so the app itself adds about 56 MB (the scene with ~1 000 items, the search index and the routing graph). The 150 MB target is therefore mostly a Qt-on-macOS baseline question. The team should measure on Windows and Linux (Task Manager / `ps`) before deciding whether to keep the target or record a decision to change it.

## Test coverage

`pytest --cov=metro` (all tests, including the slow oracle):

| Scope | Line coverage |
|---|---|
| Core (`metro/` excluding `ui/`) | 96% (target ≥ 80%) |
| Whole package including `ui/` | 95% |

`RouteWorker.compute` shows as uncovered only because coverage does not trace code running on a `QThread`; T25–T27 exercise it.

Reproduce:

```bash
pytest --cov=metro --cov-report=term-missing
```
