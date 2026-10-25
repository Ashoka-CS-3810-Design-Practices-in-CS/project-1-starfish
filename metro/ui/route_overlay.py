"""The route drawn on top of the dimmed network (FR10, FR11, [D20], [D52]).

Legs alternate between a solid line and the same colour with a white dashed centre, so
neighbouring legs can be told apart without relying on colour. Walks are dotted grey.
Every station on the route gets a small disc, and every change gets a ringed badge with a
label, so the stations and the places to change stay readable over the dimmed network.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from metro.describe import interchange_badge_text
from metro.models import Interchange, Network, Route
from metro.ui.theme import LIGHT, Theme

SOURCE_COLOUR = QColor("#1A7F37")
DESTINATION_COLOUR = QColor("#C62828")
DOT_RADIUS = 4
BADGE_RADIUS = 9
BADGE_OFFSETS = ((12, -30), (12, 10))  # label corner relative to the ring; alternate up/down
GLOW_ALPHA, GLOW_WIDTH = 80, 18  # the soft halo under a route in the dark theme


def cosmetic_pen(colour: QColor, width: float, style=Qt.PenStyle.SolidLine) -> QPen:
    """A pen whose width stays the same in pixels at every zoom level."""
    pen = QPen(colour, width, style)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


class RouteOverlay:
    """Owns the overlay items so they can be removed without touching the network."""

    def __init__(self, scene: QGraphicsScene, point_of, theme: Theme = LIGHT):
        """`point_of(station_id)` gives a station's scene position."""
        self.scene = scene
        self.point_of = point_of
        self.theme = theme
        self.items: list[QGraphicsItem] = []
        self.dots: list[QGraphicsItem] = []
        self.badges: list[QGraphicsSimpleTextItem] = []
        self.selection: list[QGraphicsItem] = []

    def draw(self, route: Route, network: Network) -> QRectF:
        """Draw the route and return its bounding rectangle in scene coordinates."""
        self.clear()
        points: list[QPointF] = []
        ride_number = 0
        for leg in route.legs:
            stops = [self.point_of(s) for s in leg.stations]
            points += stops
            if leg.kind == "WALK":
                self.add_path(stops, cosmetic_pen(QColor(self.theme.walk), 4, Qt.PenStyle.DotLine))
                continue
            colour = QColor(network.lines[leg.line_id].color)
            if self.theme.glow:
                halo = QColor(colour)
                halo.setAlpha(GLOW_ALPHA)
                self.add_path(stops, cosmetic_pen(halo, GLOW_WIDTH), 4.5)
            self.add_path(stops, cosmetic_pen(colour, 8))
            if ride_number % 2 == 1:
                self.add_path(stops, cosmetic_pen(QColor("white"), 2.5, Qt.PenStyle.DashLine))
            ride_number += 1
        for ic in route.interchanges:
            if ic.is_walk:
                walk = [self.point_of(ic.at_station), self.point_of(ic.to_station)]
                self.add_path(walk, cosmetic_pen(QColor(self.theme.walk), 4, Qt.PenStyle.DotLine))
        self.add_dots(route)
        for number, ic in enumerate(route.interchanges):
            self.add_badge(network, ic, number)
        if not points:
            return QRectF()
        xs, ys = [p.x() for p in points], [p.y() for p in points]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def add_path(self, points: list[QPointF], pen: QPen, z: float = 5) -> None:
        """Draw straight lines through consecutive points, above the network."""
        for a, b in zip(points, points[1:]):
            item = self.scene.addLine(a.x(), a.y(), b.x(), b.y(), pen)
            item.setZValue(z)
            self.items.append(item)

    def add_disc(self, station: str, radius: float, fill: QColor, pen: QPen,
                 z: float) -> QGraphicsEllipseItem:
        """A circle of constant pixel size centred on a station, tracked for clearing."""
        disc = QGraphicsEllipseItem(-radius, -radius, 2 * radius, 2 * radius)
        disc.setPos(self.point_of(station))
        disc.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        disc.setPen(pen)
        disc.setBrush(QBrush(fill))
        disc.setZValue(z)
        self.scene.addItem(disc)
        self.items.append(disc)
        return disc

    def add_dots(self, route: Route) -> None:
        """A small disc with a contrasting rim on every station the route passes."""
        seen: set[str] = set()
        for leg in route.legs:
            for station in leg.stations:
                if station not in seen:
                    seen.add(station)
                    self.dots.append(self.add_disc(
                        station, DOT_RADIUS, QColor(self.theme.dot_fill),
                        cosmetic_pen(QColor(self.theme.dot_outline), 2), 5.5))

    def add_badge(self, network: Network, ic: Interchange, number: int) -> None:
        """A heavy ring on the change station(s) and a boxed label such as '⇄ Change at X'.

        Labels of neighbouring changes alternate above and below so they rarely collide."""
        for station in dict.fromkeys((ic.at_station, ic.to_station)):
            self.add_disc(station, BADGE_RADIUS, QColor(self.theme.ring_fill),
                          cosmetic_pen(QColor(self.theme.ring_outline), 3.5), 6.5)
        label = QGraphicsSimpleTextItem(interchange_badge_text(network, ic))
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        label.setBrush(QBrush(QColor(self.theme.badge_text)))
        label.setPos(self.point_of(ic.at_station))
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        label.setTransform(label.transform().translate(*BADGE_OFFSETS[number % 2]))
        label.setZValue(7)
        box = QGraphicsRectItem(label.boundingRect().adjusted(-5, -2, 5, 2), label)
        box.setBrush(QBrush(QColor(self.theme.badge_fill)))
        box.setPen(cosmetic_pen(QColor(self.theme.ring_outline), 1.5))
        box.setFlag(QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent)
        self.scene.addItem(label)
        self.items.append(label)
        self.badges.append(label)

    def clear(self) -> None:
        """Remove every overlay item (the selection rings stay)."""
        for item in self.items:
            self.scene.removeItem(item)
        self.items = []
        self.dots = []
        self.badges = []

    def mark_selection(self, source: str | None, destination: str | None) -> None:
        """Draw a ring around the source (green, solid) and destination (red, dashed)."""
        for item in self.selection:
            self.scene.removeItem(item)
        self.selection = []
        for station, colour, style in ((source, SOURCE_COLOUR, Qt.PenStyle.SolidLine),
                                       (destination, DESTINATION_COLOUR, Qt.PenStyle.DashLine)):
            if station is None:
                continue
            ring = QGraphicsEllipseItem(-9, -9, 18, 18)
            ring.setPos(self.point_of(station))
            ring.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            ring.setPen(cosmetic_pen(colour, 3, style))
            ring.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            ring.setZValue(6)
            self.scene.addItem(ring)
            self.selection.append(ring)
