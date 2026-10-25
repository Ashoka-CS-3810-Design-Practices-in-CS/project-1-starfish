"""Route details and the message banner (FR7, FR8, FR14, [D19], [D20], [D53]).

Each leg row shows a colour swatch *and* the line name, so colour is never the only cue.
A ride with stations in between has a "▶ N stations in between" row that opens the list.
"""

from PySide6.QtCore import QEvent, Qt, Signal
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

from metro.describe import (
    between_names,
    interchange_text,
    leg_text,
    plural,
    route_steps,
    summary_text,
)
from metro.models import Interchange, Network, Route

TOGGLE_ROLE = Qt.ItemDataRole.UserRole + 1  # on a "stations in between" row: its leg's index

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
        self.route: Route | None = None
        self.expanded: set[int] = set()  # indexes in route.legs whose stations are listed
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
        # Enter is handled in eventFilter: itemActivated also fires on a single click on some
        # platforms, which would toggle a row twice.
        self.rows.installEventFilter(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary)
        layout.addWidget(self.rows, 1)
        self.show_route(None)

    def show_route(self, route: Route | None) -> None:
        """Fill the panel from a route, or empty it. Every station list starts closed."""
        self.route = route
        self.expanded = set()
        self.summary.setText("" if route is None else summary_text(route))
        self.render()

    def render(self) -> None:
        """Rebuild the rows from the route and the set of opened station lists."""
        self.rows.clear()
        if self.route is None:
            return
        for step in route_steps(self.route):
            if isinstance(step, Interchange):
                self.add_row(interchange_text(self.network, step), None, None)
                continue
            index = self.route.legs.index(step)
            colour = self.network.lines[step.line_id].color if step.line_id else None
            self.add_row(f"{index + 1}. {leg_text(self.network, step)}", step, colour)
            between = between_names(self.network, step)
            if between:
                self.add_stations(index, between)

    def add_stations(self, index: int, names: list[str]) -> None:
        """The "N stations in between" row of a leg and, when open, one row per station."""
        opened = index in self.expanded
        count = plural(len(names), "station")
        item = QListWidgetItem(f"{'▼' if opened else '▶'} {count} in between")
        item.setData(TOGGLE_ROLE, index)
        item.setData(Qt.ItemDataRole.AccessibleTextRole,
                     f"{'Hide' if opened else 'Show'} {count} in between")
        self.rows.addItem(item)
        if opened:
            for name in names:
                self.rows.addItem(QListWidgetItem(f"        · {name}"))

    def add_row(self, text: str, leg, colour: str | None) -> None:
        """One row; leg rows carry their Leg so a click can focus the map on it."""
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, leg)
        if colour:
            item.setIcon(swatch(colour))
        self.rows.addItem(item)

    def toggle(self, index: int) -> None:
        """Open or close the station list of one leg, keeping the current row."""
        row = self.rows.currentRow()
        self.expanded ^= {index}
        self.render()
        self.rows.setCurrentRow(row)

    def on_item_clicked(self, item: QListWidgetItem) -> None:
        """A station-list row opens or closes; a leg row focuses the map on that leg."""
        index = item.data(TOGGLE_ROLE)
        if index is not None:
            self.toggle(index)
            return
        leg = item.data(Qt.ItemDataRole.UserRole)
        if leg is not None:
            self.leg_clicked.emit(leg)

    def eventFilter(self, watched, event) -> bool:
        """Enter or Space on the current row does what a click on it does."""
        if (watched is self.rows and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
                and self.rows.currentItem() is not None):
            self.on_item_clicked(self.rows.currentItem())
            return True
        return super().eventFilter(watched, event)
