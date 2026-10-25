"""Which station labels to show on the map: zoom tiers [D21] and overlap suppression [D50].

Labels keep their pixel size at every zoom, so in a dense area they pile up. Candidates are
tried from the most to the least important; a label is kept only if it does not overlap one
already kept. Overlap only depends on the distances between labels, so panning never changes
the result and it needs recomputing on zoom only.
"""

from PySide6.QtCore import QRectF

CELL_PX = 64  # grid cell for the overlap test; labels span a few cells at most
PAD_PX = 2  # breathing room between neighbouring labels


def label_tier(zoom: float) -> int:
    """[D21] 0 = interchanges only, 1 = also line terminals, 2 = every station."""
    if zoom < 2:
        return 0
    return 1 if zoom < 5 else 2


def eligible(tier: int, sid: str, interchanges: set[str], terminals: set[str]) -> bool:
    """Whether the zoom tier allows a station's label at all."""
    return tier == 2 or sid in interchanges or (tier == 1 and sid in terminals)


def importance(sid: str, interchanges: set[str], terminals: set[str]) -> tuple[int, str]:
    """Sort key: interchanges first, then terminals, then the rest; the ID breaks ties so the
    outcome is the same every time."""
    return (0 if sid in interchanges else 1 if sid in terminals else 2, sid)


def cells_of(rect: QRectF) -> list[tuple[int, int]]:
    """The grid cells a rectangle touches."""
    x0, x1 = int(rect.left() // CELL_PX), int(rect.right() // CELL_PX)
    y0, y1 = int(rect.top() // CELL_PX), int(rect.bottom() // CELL_PX)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def declutter(candidates: list[tuple[str, QRectF]]) -> set[str]:
    """IDs to show, from candidates already sorted by importance (first wins an overlap)."""
    kept: set[str] = set()
    grid: dict[tuple[int, int], list[QRectF]] = {}
    for sid, rect in candidates:
        padded = rect.adjusted(-PAD_PX, -PAD_PX, PAD_PX, PAD_PX)
        cells = cells_of(padded)
        if any(padded.intersects(other) for cell in cells for other in grid.get(cell, ())):
            continue
        kept.add(sid)
        for cell in cells:
            grid.setdefault(cell, []).append(padded)
    return kept
