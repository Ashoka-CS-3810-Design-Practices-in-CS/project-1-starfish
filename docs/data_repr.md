# Data representation

All data types are frozen dataclasses (`metro/models.py`), so nothing can change them after they are built. Logic lives in plain functions. The only classes with changing state are Qt widgets and the worker.

## Network side (input)

| Type | Fields | Notes |
|---|---|---|
| `Station` | `id`, `name`, `lat`, `lon`, `aliases`, `closed`, `verified` | `id` is also the code users can search for |
| `Service` | `id`, `line_id`, `stations` (ordered), `loop` | one continuous train path; a loop also runs last → first |
| `Line` | `id`, `name`, `color`, `services` | a coloured DMRC line |
| `Segment` | `id`, `line_id`, `a`, `b`, `time_s` | the same time in both directions [A4] |
| `Walkway` | `id`, `a`, `b`, `time_s`, `one_way` | a walk between two *different* stations |
| `TransferOverride` | `station`, `service_a`, `service_b`, `time_s` | applies in both directions |
| `TransferData` | the parsed `transfers.json` | only used while loading |
| `Network` | `stations`, `lines`, `services` (dicts by ID), `segments`, `walkways`, defaults, `overrides`, `no_transfer` | every collection in sorted-ID order [D4] |

## Routing graph (`metro/graph.py`)

```python
@dataclass(frozen=True)
class RoutingGraph:
    nodes: list[tuple[str, str]]          # index -> (station_id, service_id)
    node_of: dict[tuple[str, str], int]   # (station_id, service_id) -> index
    adj: list[list[tuple[int, int, str]]] # index -> [(to, time_s, kind), ...]
    station_nodes: dict[str, list[int]]   # station -> its node indices
```

Example: station C of `toy_metro` is served by Red (R1) and Blue (B1), so it becomes two nodes joined by transfer arcs:

```
            ride 180                ride 120
  (B,R1) ─────────────── (C,R1) ─────────────── (D,R1)
                           │  ▲
                transfer   │  │  transfer
                  240      ▼  │    240
  (E,B1) ─────────────── (C,B1) ─────────────── (F,B1)
            ride 180                ride 180
```

Arriving at C on Red and leaving on Blue must use a transfer arc and pays 240 s. Riding through C on Red does not.

Why an adjacency list: Dijkstra only asks "which arcs leave this node?". The real graph has 272 nodes and 582 arcs, while a matrix would have 272² ≈ 74 000 cells, almost all empty.

## Search side (`metro/search.py`)

| Type | Fields |
|---|---|
| `IndexEntry` | `text` (normalised), `station_id`, `is_code`, `name`, `closed` |
| `Match` | `station_id`, `match_type` (CODE / NAME / PREFIX / SUBSTRING / FUZZY), `distance`, `name`, `closed` |

The index is a plain list with one entry per code, name and alias, built once at start-up.

## Route side (output)

```python
Leg(kind, line_id, service_id, stations, time_s, direction)      # RIDE or WALK
Interchange(at_station, to_station, from_line, to_line, time_s, is_walk)
Route(source, destination, legs, interchanges, total_s, stops)
```

The UI only ever receives a `Route` (or `None` for no route). Example, toy A → I (TM11):

```
Route(total_s=900, stops=4,
  legs=(Leg RIDE R1 A,B,C,D 420 "towards Station D",
        Leg RIDE Y1 H,I     180 "towards Station I"),
  interchanges=(Interchange D → H, RED → YELLOW, 300, is_walk=True),))
```

## UI state (`metro/app_state.py`)

```python
AppState(source, destination, criterion, route, computing, message, message_kind, no_route)
```

`phase` (Idle, Partial, Ready, Computing, RouteShown, NoRoute) is a property derived from these fields, not stored [D33].
