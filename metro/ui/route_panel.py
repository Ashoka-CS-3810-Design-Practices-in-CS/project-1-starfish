"""Route details and the message banner (FR7, FR8, FR14, [D19], [D20]).

Each leg row shows a colour swatch *and* the line name, so colour is never the only cue.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from metro.describe import interchange_text, leg_text, summary_text
from metro.models import Network, Route

BANNER_STYLES = {
    "error": "background: #FDECEA; color: #8C1D18; border: 1px solid #F2B8B5;",
    "info": "background: #E8F0FE; color: #174EA6; border: 1px solid #AECBFA;",
}


def swatch(colour: str) -> QIcon:
    """A small square icon in a line's colour."""
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(colour))
    return QIcon(pixmap)


class Banner(QWidget):
    """One inline message with at most one recovery button (Retry or Reset)."""

    action = Signal(str)  # the button's text

    def __init__(self, parent=None):
        """Hidden until there is a message."""
        super().__init__(parent)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setAccessibleName("Message")
        self.button = QPushButton()
        self.button.clicked.connect(lambda: self.action.emit(self.button.text()))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.button)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.hide()

    def show_message(self, text: str | None, kind: str | None, button: str | None) -> None:
        """Show `text` styled by kind ("error"/"info") with an optional button; None hides."""
        if not text:
            self.hide()
            return
        self.setStyleSheet(BANNER_STYLES.get(kind or "info", ""))
        self.text.setText(text)
        self.button.setText(button or "")
        self.button.setAccessibleName(button or "")
        self.button.setVisible(button is not None)
        self.show()


class RoutePanel(QWidget):
    """Summary line plus one row per leg and per interchange. Emits `leg_clicked(leg)`."""

    leg_clicked = Signal(object)

    def __init__(self, network: Network, parent=None):
        """Empty until a route is shown."""
        super().__init__(parent)
        self.network = network
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setAccessibleName("Route summary")
        font = self.summary.font()
        font.setBold(True)
        self.summary.setFont(font)
        self.rows = QListWidget()
        self.rows.setAccessibleName("Route steps")
        self.rows.setWordWrap(True)
        self.rows.itemClicked.connect(self.on_item_clicked)
        self.rows.itemActivated.connect(self.on_item_clicked)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary)
        layout.addWidget(self.rows, 1)
        self.show_route(None)

    def show_route(self, route: Route | None) -> None:
        """Fill the panel from a route, or empty it."""
        self.rows.clear()
        if route is None:
            self.summary.setText("")
            return
        self.summary.setText(summary_text(route))
        changes = iter(route.interchanges)
        rides = 0
        for number, leg in enumerate(route.legs, start=1):
            if leg.kind == "RIDE":
                if rides > 0:
                    self.add_row(interchange_text(self.network, next(changes)), None, None)
                rides += 1
            colour = self.network.lines[leg.line_id].color if leg.line_id else None
            self.add_row(f"{number}. {leg_text(self.network, leg)}", leg, colour)

    def add_row(self, text: str, leg, colour: str | None) -> None:
        """One row; leg rows carry their Leg so a click can focus the map on it."""
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, leg)
        if colour:
            item.setIcon(swatch(colour))
        self.rows.addItem(item)

    def on_item_clicked(self, item: QListWidgetItem) -> None:
        """Clicking (or pressing Enter on) a leg focuses the map on it."""
        leg = item.data(Qt.ItemDataRole.UserRole)
        if leg is not None:
            self.leg_clicked.emit(leg)
