"""Route details and the message banner (FR7, FR8, FR14, [D19], [D20], [D53], [D56]).

Each leg row shows a colour swatch *and* the line name, so colour is never the only cue.
A ride with stations in between has a "▶ N stations in between" row that opens the list.
When there are alternative routes, tabs above the summary switch between them.
"""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from metro.alternatives import route_badges
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
        self.setObjectName("banner")  # coloured by the theme's style sheet, by kind
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.hide()

    def show_message(self, text: str | None, kind: str | None, button: str | None) -> None:
        """Show `text` styled by kind ("error"/"info") with an optional button; None hides."""
        if not text:
            self.hide()
            return
        self.setProperty("kind", kind or "info")
        self.style().unpolish(self)  # make Qt re-read the style sheet for the new kind
        self.style().polish(self)
        self.text.setText(text)
        self.button.setText(button or "")
        self.button.setAccessibleName(button or "")
        self.button.setVisible(button is not None)
        self.show()


class RoutePanel(QWidget):
    """Summary line plus one row per leg and per interchange. Emits `leg_clicked(leg)`."""

    leg_clicked = Signal(object)
    alternative_chosen = Signal(int)  # index in the alternatives
    compare_requested = Signal()

    def __init__(self, network: Network, parent=None):
        """Empty until a route is shown."""
        super().__init__(parent)
        self.network = network
        self.route: Route | None = None
        self.tabs = QTabBar()
        self.tabs.setAccessibleName("Alternative routes")
        self.tabs.setExpanding(True)
        self.tabs.setUsesScrollButtons(False)  # three short tabs always fit in the panel
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.hide()
        self.caption = QLabel()  # what the selected route is best at; tabs have no room for it
        self.caption.setAccessibleName("What this route is best at")
        self.caption.hide()
        self.badges: list[tuple[str, ...]] = []
        self.compare_button = QPushButton("Compare routes")
        self.compare_button.setAccessibleName("Compare routes")
        self.compare_button.clicked.connect(self.compare_requested)
        self.compare_button.hide()
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
        layout.addWidget(self.tabs)
        layout.addWidget(self.caption)
        layout.addWidget(self.summary)
        layout.addWidget(self.rows, 1)
        layout.addWidget(self.compare_button)
        self.show_route(None)

    def show_alternatives(self, routes: tuple[Route, ...], selected: int) -> None:
        """One tab per alternative and, under them, what the selected route is best at; all
        hidden when there is nothing to choose between. Setting the tab here does not send
        `alternative_chosen`."""
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        self.badges = route_badges(list(routes))
        for number, (route, badges) in enumerate(zip(routes, self.badges), 1):
            self.tabs.addTab(f"Route {number}")
            self.tabs.setTabToolTip(number - 1, f"{summary_text(route)}"
                                    + (f" - {', '.join(badges)}" if badges else ""))
        if routes:
            self.tabs.setCurrentIndex(selected)
        self.tabs.blockSignals(False)
        self.update_caption()
        many = len(routes) > 1
        for widget in (self.tabs, self.caption, self.compare_button):
            widget.setVisible(many)

    def on_tab_changed(self, index: int) -> None:
        """The user picked a tab: update the caption and tell the window."""
        self.update_caption()
        self.alternative_chosen.emit(index)

    def update_caption(self) -> None:
        """'Best at: Fastest, Fewest interchanges' for the selected tab."""
        index = self.tabs.currentIndex()
        best = self.badges[index] if 0 <= index < len(self.badges) else ()
        self.caption.setText("Best at: " + (", ".join(best) if best else "-"))

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
