# Algorithms

The algorithms of A2 as built, with the simplifications of [D26]–[D35]. Each section gives the problem, pseudocode, why it is correct, and its cost. N = nodes of the routing graph (272 on the real data), A = arcs (582), S = stations (244).

---

## Algorithm 1 — Load and validate (`metro/data.py`, `metro/validate.py`)

**Problem.** Turn four JSON files into a `Network`, or explain *every* problem in them (FR1, ER8–ER10).

```
load_network(folder):
    raw ← read each file           # DatasetUnreadable if missing / not JSON (check 1)
    problems ← []
    parse each file entry by entry:
        report missing / mistyped fields          (check 2)
        report duplicate IDs                      (check 3)
        report times outside 10..600 s            (check 5)
        report coordinates outside the NCR box    (check 9)
    cross-file checks:
        unknown station / line / service IDs      (check 4)
        service hop without a segment             (check 6)
        segment used by no service                (check 7)
        station on no service and no walkway      (check 8)
        override naming a service not at station  (check 10)
    if problems: raise DataError(problems)
    build Network with every collection sorted by ID   ([D4])
    if not is_connected(network): log a warning        (check 11, UC5)
```

**Why it is correct.** Each check is independent and only appends, so one problem never hides another. IDs of stations with a broken field are still recorded as known, so a bad `lat` does not cause extra "unknown station" problems elsewhere.

**Cost.** O(file size). Each check is one pass with set or dictionary lookups. About 3 ms on the real data.

---

## Algorithm 2 — Build the line-expanded graph (`metro/graph.py`)

**Problem.** Charge interchanges correctly (FR2, FR6). In a plain station graph, "arrive on Red, leave on Blue" and "stay on Red" look the same.

```
build_graph(network):
    nodes ← sorted {(station, service) : station is open and on service}   # [D1]
    for each service, each hop (a, b) incl. a loop's closing hop:
        if both ends open: add ride arc a→b and b→a with the segment time
    for each station, each ordered pair of its services (s1, s2), s1 ≠ s2:
        if {s1, s2} not in no_transfer: add transfer arc with transfer_time(...)
    for each walkway (a, b): add walk arcs from every node of a to every node of b
                             (and back unless one_way)                       # [D2]
    sort every adjacency list
```

`transfer_time`: an override for that station and pair wins; otherwise 120 s for two services of the same line (a branch change) and 240 s for different lines.

**Why it is correct.** Riding a service never changes node service; the only way to change service is a transfer or walk arc, so every change is paid for exactly once. A closed station has no node, so no path can pass through it.

**Cost.** O(N + A + Σ k²) where k is the number of services at a station (at most 3 here). Toy fixtures: 11 nodes / 22 arcs (TM0) and 10 / 20 (TL0).

---

## Algorithm 3 — Lexicographic Dijkstra (`metro/router.py: find_route`)

**Problem.** The best route by a criterion, with ties broken by the other two measures (FR6, FR16).

The cost of a path is a tuple **(time_s, changes, stops)**. A ride arc adds (t, 0, 1); a transfer or walk arc adds (t, 1, 0) [D17]. Each criterion only reorders the tuple for the heap:

| Criterion | Heap key |
|---|---|
| fastest | (time, changes, stops) |
| fewest_changes | (changes, time, stops) |
| fewest_stops | (stops, time, changes) |

```
find_route(graph, network, src, dst, criterion, cancel):
    for each node n of src: cost[n] ← (0,0,0); push ((0,0,0), n)    # super-source
    while heap not empty:
        key, n ← pop
        every 256 pops: if cancel is set: raise RouteCancelled          # [D5]
        if key > key_of(cost[n]): continue                              # lazy deletion
        if station(n) = dst: return assemble_route(path to n)          # early exit
        for (m, t, kind) in adj[n]:
            new ← cost[n] + arc_cost(t, kind)
            if m unseen or key_of(new) < key_of(cost[m]):
                cost[m] ← new; prev[m] ← (n, t, kind); push (key_of(new), m)
    return None                                                         # ER7
```

**Why it is correct.** Dijkstra needs costs that never decrease along a path. Every arc cost is a tuple of non-negative numbers, and adding such a tuple never makes a tuple lexicographically smaller, so the usual proof carries over. The super-source starts every node of `src` at zero, so no change is charged at the origin. Early exit returns the first popped node of `dst`; a transfer at the destination would only produce a more expensive node of the same station, so no false change is added there (TM3). Heap entries are `(key, node)` and nodes are numbered from sorted IDs, so equal keys always break the same way (TL5, T10).

**Cost.** O((N + A) log N) per query; `cost` and `prev` are dictionaries, so a query touches only what it explores [D3]. Measured p95: 0.25 ms on the real data, 3.3 ms on the 2 600-station synthetic network (T29, T30).

---

## Algorithm 4 — Route assembly (`metro/router.py: assemble_route`)

**Problem.** Turn a list of arcs into legs and interchanges a person can follow (FR7, FR8).

```
pieces ← split arcs into: runs of ride arcs on one service | single transfer arcs | single walk arcs
rides ← positions of ride pieces
walks before the first ride and after the last ride → WALK legs        # [D17]
each ride piece → RIDE leg (stations, time, direction label)
everything between two consecutive ride pieces → one Interchange
    (is_walk if it contains a walk arc; time = sum of those arcs)
check invariants
```

**Invariants (asserted in `check_invariants`).**
1. Every RIDE leg has at least two stations.
2. `len(interchanges) == number of RIDE legs − 1` (or 0).
3. `sum(leg times) + sum(interchange times) == total_s`.

**Direction label [D14].** For a normal service: "towards" the last station if travelling in list order, otherwise the first. For a loop there is no terminus, so the label names the next interchange station in the direction of travel.

**Display minutes.** `(seconds + 30) // 60`, always computed from total seconds, never by adding rounded leg minutes.

**Cost.** O(path length).

---

## Algorithm 5 — Station search (`metro/search.py`), simplified [D26]

**Problem.** Find stations by name, alias or code, tolerating typos (FR3, ER2–ER4).

```
normalise(text): cut to 100 chars → NFKC → whitespace to spaces → drop control chars
                 → lowercase, collapse spaces → whole-word "sec" → "sector"

search(index, query):
    q ← normalise(query); if q empty: return []
    k ← min(2, len(q) // 3)                                  # [D16]
    for each entry (text, station, is_code) in index:
        CODE      if is_code and q = text
        NAME      if q = text
        PREFIX    if text starts with q
        SUBSTRING if q in text
        FUZZY     if edit distance(q, text or its first len(q) chars) ≤ k
    keep each station's best match; sort by (rank, distance, name); return first 8
```

**Fuzzy threshold [D16].** No fuzzy matching below 3 characters (one edit could reach almost anything), k = 1 for 3–5 characters, k = 2 from 6.

**Banded Levenshtein.** The classic two-row dynamic programme, stopping as soon as every value in a row exceeds k. Each cell is at least the smallest value of the row above, so a row that is entirely above k means the answer is too. A length difference above k is rejected before starting.

**Why a linear scan [D26].** About 1 000 index entries; p95 is about 4 ms per keystroke against a 50 ms budget. A trie with cached top-8 lists would add code for no measurable gain.

**Cost.** O(entries × k × |q|) in practice, thanks to the early stop.

---

## Algorithm 8 — Floyd–Warshall oracle (`tests/oracle.py`)

**Problem.** An independent check of Dijkstra's times on the toy fixtures [D28].

```
dist[i][j] ← min arc time i→j, 0 on the diagonal, ∞ otherwise
for k, i, j: dist[i][j] ← min(dist[i][j], dist[i][k] + dist[k][j])
time(s, t) ← min over nodes i of s, nodes j of t of dist[i][j]
```

It uses time only, no super-source and no early exit, so it shares no code or shortcuts with the router. On the real data the independent oracle is networkx's Dijkstra on a copy of the graph with a super-source and per-station super-sinks (T19, all 59 000 ordered pairs).

**Cost.** O(N³), fine for 10–11 nodes.

---

## [D17] Walk legs versus walk interchanges

A walk *between* two rides is an interchange (`is_walk=True`), because the rider changes train. A walk at the very start or end of the journey is a WALK leg and is **not** an interchange: nothing has been boarded yet, or the journey is over. In the search key every walk still counts as a change, so the search avoids pointless walks; that is why the reported interchange count can be lower than the key's count, never higher (T21).
