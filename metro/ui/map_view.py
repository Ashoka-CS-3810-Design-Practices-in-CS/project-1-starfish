"""Interactive map of the network (FR9–FR12, [D21], [D27], ER11, ER12).

Qt does the hard parts for us [D27]: zoom about the cursor (AnchorUnderMouse), panning
(ScrollHandDrag) and spatial look-ups (`items(rect)` uses Qt's BSP tree).
"""

import logging
import math

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QToolTip

from metro.describe import station_lines, station_tooltip
from metro.graph import interchange_stations
from metro.models import Leg, Network, Route
from metro.ui.map_controls import MapControls
from metro.ui.map_labels import declutter, eligible, importance, label_tier
from metro.ui.network_items import LABEL_OFFSET, draw_network
from metro.ui.route_overlay import RouteOverlay

log = logging.getLogger(__name__)

K = 10_000  # scene units per degree (PRD §6.2)
MIN_ZOOM, MAX_ZOOM = 0.2, 20.0  # allowed scale, as a multiple of the fit scale
ZOOM_STEP = 1.15  # per wheel notch (120 units of angleDelta)
HOVER_RADIUS_PX = 8
CLICK_SLOP_PX = 4  # a press and release closer than this is a click, not a drag
BACKGROUND = QColor("#FAFAF7")


def projection_origin(network: Network) -> tuple[float, float]:
    """(lat0, lon0): the mean of all station coordinates."""
    stations = list(network.stations.values())
    return (sum(s.lat for s in stations) / len(stations),
            sum(s.lon for s in stations) / len(stations))


def project(lat: float, lon: float, origin: tuple[float, float]) -> QPointF:
    """Equirectangular projection: x grows east, y grows south (screen convention)."""
    lat0, lon0 = origin
    return QPointF((lon - lon0) * math.cos(math.radians(lat0)) * K, -(lat - lat0) * K)


class MapView(QGraphicsView):
    """The map widget. Emits `station_clicked(station_id)` and `zoom_changed(percent)`."""

    station_clicked = Signal(str)
    zoom_changed = Signal(int)

    def __init__(self, network: Network, parent=None):
        """Draw the whole network once; routes are later drawn on top, never rebuilt."""
        super().__init__(parent)
        self.network = network
        self.origin = projection_origin(network)
        self.lines_at = station_lines(network)
        self.fit_scale = 1.0
        self.tier = -1
        self.press_pos: QPoint | None = None
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(BACKGROUND)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName("Metro map")
        self.setToolTip("Click a station to choose it. Scroll or + / - to zoom, 0 to fit.")
        self.network_items, self.markers, self.labels = draw_network(
            self.scene(), network, self.point_of)
        self.overlay = RouteOverlay(self.scene(), self.point_of)
        self.controls = MapControls(self)
        self.controls.zoom_in.connect(lambda: self.zoom_by(ZOOM_STEP))
        self.controls.zoom_out.connect(lambda: self.zoom_by(1 / ZOOM_STEP))
        self.controls.fit.connect(self.fit_all)

    # ---- drawing the network ----------------------------------------------------------

    def point_of(self, station_id: str) -> QPointF:
        """Scene position of a station."""
        st = self.network.stations[station_id]
        return project(st.lat, st.lon, self.origin)

    def update_labels(self) -> None:
        """Show the labels the zoom tier allows, minus those that would overlap a more
        important one [D21], [D50]. Panning cannot change the result, only zooming."""
        tier = label_tier(self.zoom())
        self.tier = tier
        interchanges = interchange_stations(self.network)
        terminals = {s.stations[i] for s in self.network.services.values()
                     if not s.loop for i in (0, -1)}
        ordered = sorted((sid for sid in self.labels if eligible(tier, sid, interchanges,
                                                                 terminals)),
                         key=lambda sid: importance(sid, interchanges, terminals))
        keep = declutter([(sid, self.label_rect(sid)) for sid in ordered])
        for sid, label in self.labels.items():
            label.setVisible(sid in keep)

    def label_rect(self, sid: str) -> QRectF:
        """Where a station's label would be drawn, in view pixels."""
        origin = self.mapFromScene(self.point_of(sid))
        size = self.labels[sid].boundingRect()
        return QRectF(origin.x() + LABEL_OFFSET[0], origin.y() + LABEL_OFFSET[1],
                      size.width(), size.height())

    # ---- zoom and fit -----------------------------------------------------------------

    def zoom(self) -> float:
        """Current scale as a multiple of the fit scale (1.0 = whole network fits)."""
        return self.transform().m11() / self.fit_scale

    def viewport_is_empty(self) -> bool:
        """True when the viewport has zero width or height (ER11)."""
        return self.viewport().width() <= 0 or self.viewport().height() <= 0

    def fit_all(self) -> None:
        """Fit the whole network in the view and make that the reference zoom."""
        if self.viewport_is_empty():
            log.info("Fit skipped: the map viewport is 0 x 0.")
            return
        self.fit_with_margin(self.scene().itemsBoundingRect())
        self.fit_scale = self.transform().m11()  # the new reference for zoom limits
        self.after_zoom()

    def fit_rect(self, rect: QRectF) -> None:
        """Fit a scene rectangle (a route or a leg), then keep the zoom inside its limits."""
        if self.viewport_is_empty():
            log.info("Fit skipped: the map viewport is 0 x 0.")
            return
        self.fit_with_margin(rect)
        self.zoom_by(1.0)  # zooming by 1.0 applies the clamp and refreshes the labels

    def fit_with_margin(self, rect: QRectF) -> None:
        """fitInView with an 8% margin, so nothing touches the edge of the view."""
        margin = max(rect.width(), rect.height(), 200) * 0.08
        self.fitInView(rect.adjusted(-margin, -margin, margin, margin),
                       Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_by(self, factor: float) -> None:
        """Zoom by `factor`, clamped to [MIN_ZOOM, MAX_ZOOM] times the fit scale."""
        target = min(max(self.zoom() * factor, MIN_ZOOM), MAX_ZOOM)
        step = target / self.zoom()
        self.scale(step, step)
        self.after_zoom()

    def after_zoom(self) -> None:
        """Refresh labels and tell the status bar the new zoom."""
        self.update_labels()
        self.zoom_changed.emit(round(self.zoom() * 100))

    # ---- route overlay ----------------------------------------------------------------

    def show_route(self, route: Route) -> None:
        """Dim the network to 25% and draw the route on top, then fit to it."""
        for item in self.network_items:
            item.setOpacity(0.25)
        rect = self.overlay.draw(route, self.network)
        self.fit_rect(rect)

    def clear_route(self) -> None:
        """Remove the route overlay and restore full opacity."""
        self.overlay.clear()
        for item in self.network_items:
            item.setOpacity(1.0)
        for sid, st in self.network.stations.items():
            if st.closed:
                self.markers[sid].setOpacity(0.5)

    def focus_leg(self, leg: Leg) -> None:
        """Fit the view to one leg of the route (clicking a leg in the panel)."""
        points = [self.point_of(s) for s in leg.stations]
        xs, ys = [p.x() for p in points], [p.y() for p in points]
        self.fit_rect(QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))

    def set_selection(self, source: str | None, destination: str | None) -> None:
        """Ring the chosen source and destination stations."""
        self.overlay.mark_selection(source, destination)

    # ---- mouse and keyboard -------------------------------------------------------------

    def stations_near(self, pos: QPoint) -> list[str]:
        """Station IDs whose markers are within 8 px of a view position, nearest first."""
        r = HOVER_RADIUS_PX
        found = {item.data(0) for item in self.items(QRect(pos.x() - r, pos.y() - r, 2 * r, 2 * r))
                 if item.data(0) in self.markers}

        def distance(sid: str) -> float:
            p = self.mapFromScene(self.point_of(sid))
            return math.hypot(p.x() - pos.x(), p.y() - pos.y())
        return sorted(found, key=lambda sid: (distance(sid), sid))

    def tooltip_at(self, pos: QPoint) -> str:
        """Tooltip text for a view position: every nearby station, nearest first."""
        return "\n\n".join(station_tooltip(self.network, sid, self.lines_at[sid])
                           for sid in self.stations_near(pos))

    def wheelEvent(self, event) -> None:
        """Zoom by 1.15 per notch; ignore zero or non-finite deltas (ER11)."""
        delta = event.angleDelta().y()
        if delta == 0 or not math.isfinite(delta):
            log.info("Ignored wheel event with delta %r.", delta)
            return
        self.zoom_by(ZOOM_STEP ** (delta / 120))

    def keyPressEvent(self, event) -> None:
        """+ and - zoom, 0 fits; arrow keys pan (handled by QGraphicsView)."""
        key = event.key()
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_by(ZOOM_STEP)
        elif key == Qt.Key.Key_Minus:
            self.zoom_by(1 / ZOOM_STEP)
        elif key == Qt.Key.Key_0:
            self.fit_all()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Double-click zooms in about the cursor."""
        self.zoom_by(ZOOM_STEP ** 3)

    def mousePressEvent(self, event) -> None:
        """Remember where the press happened, to tell a click from a drag."""
        self.press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """A release near the press position is a click: choose the nearest station."""
        super().mouseReleaseEvent(event)
        pos = event.position().toPoint()
        if self.press_pos is not None and \
                (pos - self.press_pos).manhattanLength() <= CLICK_SLOP_PX:
            near = self.stations_near(pos)
            if near:
                self.station_clicked.emit(near[0])
        self.press_pos = None

    def mouseMoveEvent(self, event) -> None:
        """Show a tooltip for the stations under the cursor (FR12, ER12)."""
        super().mouseMoveEvent(event)
        text = self.tooltip_at(event.position().toPoint())
        if text:
            QToolTip.showText(event.globalPosition().toPoint(), text, self)
        else:
            QToolTip.hideText()

    def resizeEvent(self, event) -> None:
        """Keep the controls in the top-right corner; fit the network the first time the
        view gets a real size."""
        super().resizeEvent(event)
        self.controls.move(self.width() - self.controls.width() - 12, 12)
        if self.tier == -1 and not self.viewport_is_empty():
            self.fit_all()
