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
from metro.ui.theme import LIGHT, Theme

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


def style_marker(marker: QGraphicsEllipseItem, big: bool, closed: bool, theme: Theme) -> None:
    """Colours of a station dot: interchanges light, closed stations grey. Leaves opacity
    alone, because that belongs to the route dimming."""
    marker.setPen(QPen(QColor(theme.marker_outline), 1.5))
    fill = theme.closed_fill if closed else theme.interchange_fill if big else theme.marker_fill
    marker.setBrush(QBrush(QColor(fill)))


def make_marker(sid: str, big: bool, closed: bool, position, theme: Theme) -> QGraphicsEllipseItem:
    """A station dot of constant pixel size; interchanges larger."""
    radius = 5 if big else 3
    marker = QGraphicsEllipseItem(-radius, -radius, 2 * radius, 2 * radius)
    marker.setPos(position)
    marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
    style_marker(marker, big, closed, theme)
    if closed:
        marker.setOpacity(0.5)
    marker.setZValue(2)
    marker.setData(0, sid)
    return marker


def make_label(name: str, position, theme: Theme) -> QGraphicsSimpleTextItem:
    """A label that keeps its pixel size at every zoom, offset to the marker's right."""
    label = QGraphicsSimpleTextItem(name)
    label.setBrush(QBrush(QColor(theme.label)))
    label.setPos(position)
    label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
    label.setTransform(label.transform().translate(*LABEL_OFFSET))
    label.setZValue(3)
    return label


def restyle(network: Network, markers: dict, labels: dict, theme: Theme) -> None:
    """Apply a theme to the markers and labels already in the scene."""
    interchanges = interchange_stations(network)
    for sid, station in network.stations.items():
        style_marker(markers[sid], sid in interchanges, station.closed, theme)
        labels[sid].setBrush(QBrush(QColor(theme.label)))


def draw_network(scene: QGraphicsScene, network: Network, point_of,
                 theme: Theme = LIGHT) -> tuple[
        list[QGraphicsItem], dict[str, QGraphicsEllipseItem], dict[str, QGraphicsSimpleTextItem]]:
    """Add the whole network to the scene; returns (all items, markers by ID, labels by ID)."""
    items = draw_segments(scene, network, point_of)
    interchanges = interchange_stations(network)
    markers: dict[str, QGraphicsEllipseItem] = {}
    labels: dict[str, QGraphicsSimpleTextItem] = {}
    for sid, station in network.stations.items():
        markers[sid] = make_marker(sid, sid in interchanges, station.closed, point_of(sid),
                                   theme)
        labels[sid] = make_label(station.name, point_of(sid), theme)
        scene.addItem(markers[sid])
        scene.addItem(labels[sid])
        items += [markers[sid], labels[sid]]
    return items, markers, labels
