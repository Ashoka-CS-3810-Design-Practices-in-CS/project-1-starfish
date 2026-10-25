"""The always-present drawing of the network: line segments, station markers and labels.

Built once when the map is created; routes are drawn on top of it later and never rebuild it.
"""

from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
)

from metro.graph import interchange_stations
from metro.models import Network

LABEL_COLOUR = QColor("#222222")
LABEL_OFFSET = (7, -8)  # label's top-left relative to its marker, in pixels


def draw_segments(scene: QGraphicsScene, network: Network, point_of) -> list[QGraphicsItem]:
    """One line item per segment in its line colour, with a cosmetic (fixed-width) pen."""
    items = []
    for seg in network.segments:
        pen = QPen(QColor(network.lines[seg.line_id].color), 3)
        pen.setCosmetic(True)
        a, b = point_of(seg.a), point_of(seg.b)
        item = scene.addLine(a.x(), a.y(), b.x(), b.y(), pen)
        item.setZValue(0)
        items.append(item)
    return items


def make_marker(sid: str, big: bool, closed: bool, position) -> QGraphicsEllipseItem:
    """A station dot of constant pixel size; interchanges larger and white, closed grey."""
    radius = 5 if big else 3
    marker = QGraphicsEllipseItem(-radius, -radius, 2 * radius, 2 * radius)
    marker.setPos(position)
    marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
    marker.setPen(QPen(QColor("#333333"), 1.5))
    marker.setBrush(QBrush(QColor("white" if big else "#555555")))
    if closed:
        marker.setBrush(QBrush(QColor("#BBBBBB")))
        marker.setOpacity(0.5)
    marker.setZValue(2)
    marker.setData(0, sid)
    return marker


def make_label(name: str, position) -> QGraphicsSimpleTextItem:
    """A label that keeps its pixel size at every zoom, offset to the marker's right."""
    label = QGraphicsSimpleTextItem(name)
    label.setBrush(QBrush(LABEL_COLOUR))
    label.setPos(position)
    label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
    label.setTransform(label.transform().translate(*LABEL_OFFSET))
    label.setZValue(3)
    return label


def draw_network(scene: QGraphicsScene, network: Network, point_of) -> tuple[
        list[QGraphicsItem], dict[str, QGraphicsEllipseItem], dict[str, QGraphicsSimpleTextItem]]:
    """Add the whole network to the scene; returns (all items, markers by ID, labels by ID)."""
    items = draw_segments(scene, network, point_of)
    interchanges = interchange_stations(network)
    markers: dict[str, QGraphicsEllipseItem] = {}
    labels: dict[str, QGraphicsSimpleTextItem] = {}
    for sid, station in network.stations.items():
        markers[sid] = make_marker(sid, sid in interchanges, station.closed, point_of(sid))
        labels[sid] = make_label(station.name, point_of(sid))
        scene.addItem(markers[sid])
        scene.addItem(labels[sid])
        items += [markers[sid], labels[sid]]
    return items, markers, labels
