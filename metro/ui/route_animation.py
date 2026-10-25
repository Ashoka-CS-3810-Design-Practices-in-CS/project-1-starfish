"""A marker that travels along the route on the map (Could tier, [D58]).

The geometry (`path_points`, `point_at`, `vertex_fractions`) is plain functions on points, so it
is tested without a timer. `RouteAnimator` owns the marker and a timer; the timer only calls
`advance(ms)`, and tests call it directly instead of waiting.
"""

import math
from bisect import bisect_right

from PySide6.QtCore import QObject, QPointF, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene

from metro.models import Route

TICK_MS = 16  # about 60 frames a second
MS_PER_STOP = 250  # the trip takes this long per station, within the limits below
MIN_MS, MAX_MS = 3000, 15000
MARKER_RADIUS = 7
EPS = 1e-9


def path_points(route: Route, point_of) -> list[QPointF]:
    """The route as one polyline in travel order, one point per station.

    Consecutive legs share their change station, so those repeats are dropped; a walk between
    two stations stays as the straight segment between them."""
    points: list[QPointF] = []
    for leg in route.legs:
        for station in leg.stations:
            point = point_of(station)
            if not points or points[-1] != point:
                points.append(point)
    return points


def cumulative_lengths(points: list[QPointF]) -> list[float]:
    """Distance along the polyline at each point; the first is 0."""
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.hypot(b.x() - a.x(), b.y() - a.y()))
    return lengths


def point_at(points: list[QPointF], lengths: list[float], fraction: float) -> QPointF:
    """The point `fraction` (0 to 1, clamped) of the way along the polyline."""
    total = lengths[-1]
    if total <= 0:
        return points[0]
    target = min(max(fraction, 0.0), 1.0) * total
    i = min(max(bisect_right(lengths, target) - 1, 0), len(points) - 2)
    span = lengths[i + 1] - lengths[i]
    t = 0.0 if span <= 0 else (target - lengths[i]) / span
    a, b = points[i], points[i + 1]
    return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)


def vertex_fractions(lengths: list[float]) -> list[float]:
    """Where each station lies along the path, as a fraction from 0 to 1."""
    total = lengths[-1]
    return [0.0 for _ in lengths] if total <= 0 else [d / total for d in lengths]


def duration_ms(point_count: int) -> int:
    """How long the whole trip takes: proportional to the stations, kept watchable."""
    return min(max((point_count - 1) * MS_PER_STOP, MIN_MS), MAX_MS)


class RouteAnimator(QObject):
    """Moves one marker along a route. Emits `playing_changed(bool)`."""

    playing_changed = Signal(bool)

    def __init__(self, scene: QGraphicsScene, point_of, parent=None):
        """The marker exists from the start but stays hidden until there is a route."""
        super().__init__(parent)
        self.point_of = point_of
        self.points: list[QPointF] = []
        self.lengths: list[float] = [0.0]
        self.fraction = 0.0
        self.playing = False
        self.marker = QGraphicsEllipseItem(-MARKER_RADIUS, -MARKER_RADIUS,
                                           2 * MARKER_RADIUS, 2 * MARKER_RADIUS)
        self.marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.marker.setBrush(QBrush(QColor("#E53935")))
        pen = QPen(QColor("white"), 3)
        pen.setCosmetic(True)
        self.marker.setPen(pen)
        self.marker.setZValue(8)  # above route lines, dots and badges
        self.marker.hide()
        scene.addItem(self.marker)
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(lambda: self.advance(TICK_MS))

    @property
    def ready(self) -> bool:
        """True when there is a route with some length to travel."""
        return len(self.points) > 1 and self.lengths[-1] > 0

    def set_route(self, route: Route) -> None:
        """Put the marker at the start of a new route (stops any trip in progress)."""
        self.pause()
        self.points = path_points(route, self.point_of)
        self.lengths = cumulative_lengths(self.points)
        self.fraction = 0.0
        self.marker.setVisible(self.ready)
        self.place()

    def clear(self) -> None:
        """No route: stop and hide the marker."""
        self.pause()
        self.points, self.lengths, self.fraction = [], [0.0], 0.0
        self.marker.hide()

    def place(self) -> None:
        """Move the marker to the current fraction."""
        if self.points:
            self.marker.setPos(point_at(self.points, self.lengths, self.fraction))

    def play(self) -> None:
        """Start, resume, or start again if the last trip reached the end."""
        if not self.ready:
            return
        if self.fraction >= 1.0:
            self.fraction = 0.0
        self.timer.start()
        self.set_playing(True)

    def pause(self) -> None:
        """Stop where it is."""
        self.timer.stop()
        self.set_playing(False)

    def toggle(self) -> None:
        """Play if paused, pause if playing."""
        if self.playing:
            self.pause()
        else:
            self.play()

    def set_playing(self, playing: bool) -> None:
        """Remember the state and tell listeners only when it changes."""
        if playing != self.playing:
            self.playing = playing
            self.playing_changed.emit(playing)

    def advance(self, ms: int) -> None:
        """Move on by `ms` of the trip; stop at the end."""
        if not self.ready:
            return
        self.fraction = min(self.fraction + ms / duration_ms(len(self.points)), 1.0)
        self.place()
        if self.fraction >= 1.0:
            self.pause()

    def step(self, direction: int) -> None:
        """Pause and jump to the next (+1) or previous (-1) station on the route."""
        if not self.ready:
            return
        self.pause()
        marks = vertex_fractions(self.lengths)
        if direction > 0:
            ahead = [m for m in marks if m > self.fraction + EPS]
            self.fraction = ahead[0] if ahead else 1.0
        else:
            behind = [m for m in marks if m < self.fraction - EPS]
            self.fraction = behind[-1] if behind else 0.0
        self.place()
