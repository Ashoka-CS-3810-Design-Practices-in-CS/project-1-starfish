"""The route drawn on top of the dimmed network (FR10, [D20]).

Legs alternate between a solid line and the same colour with a white dashed centre, so
neighbouring legs can be told apart without relying on colour. Walks are dotted grey.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsScene

from metro.models import Network, Route

WALK_COLOUR = QColor("#666666")
SOURCE_COLOUR = QColor("#1A7F37")
DESTINATION_COLOUR = QColor("#C62828")


def cosmetic_pen(colour: QColor, width: float, style=Qt.PenStyle.SolidLine) -> QPen:
    """A pen whose width stays the same in pixels at every zoom level."""
    pen = QPen(colour, width, style)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


class RouteOverlay:
    """Owns the overlay items so they can be removed without touching the network."""

    def __init__(self, scene: QGraphicsScene, point_of):
        """`point_of(station_id)` gives a station's scene position."""
        self.scene = scene
        self.point_of = point_of
        self.items: list[QGraphicsItem] = []
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
                self.add_path(stops, cosmetic_pen(WALK_COLOUR, 4, Qt.PenStyle.DotLine))
                continue
            colour = QColor(network.lines[leg.line_id].color)
            self.add_path(stops, cosmetic_pen(colour, 8))
            if ride_number % 2 == 1:
                self.add_path(stops, cosmetic_pen(QColor("white"), 2.5, Qt.PenStyle.DashLine))
            ride_number += 1
        for ic in route.interchanges:
            if ic.is_walk:
                walk = [self.point_of(ic.at_station), self.point_of(ic.to_station)]
                self.add_path(walk, cosmetic_pen(WALK_COLOUR, 4, Qt.PenStyle.DotLine))
        if not points:
            return QRectF()
        xs, ys = [p.x() for p in points], [p.y() for p in points]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def add_path(self, points: list[QPointF], pen: QPen) -> None:
        """Draw straight lines through consecutive points, above the network."""
        for a, b in zip(points, points[1:]):
            item = self.scene.addLine(a.x(), a.y(), b.x(), b.y(), pen)
            item.setZValue(5)
            self.items.append(item)

    def clear(self) -> None:
        """Remove every overlay item (the selection rings stay)."""
        for item in self.items:
            self.scene.removeItem(item)
        self.items = []

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
