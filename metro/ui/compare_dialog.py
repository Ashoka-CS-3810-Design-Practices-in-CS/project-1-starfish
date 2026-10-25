"""Side-by-side comparison of the routes found for one journey (Could tier, FR17, [D56]).

One column per route, one row per measure. The best value in a row is bold, decided by the
same badges the route tabs use, so the two can never disagree. Not modal.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from metro.alternatives import route_badges
from metro.describe import lines_used, route_title
from metro.models import Network, Route
from metro.router import minutes

MEASURES = (("Travel time", "Fastest"), ("Interchanges", "Fewest interchanges"),
            ("Stops", "Fewest stops"))  # (row label, the badge that makes it bold)
ROW_LINES, ROW_BEST, ROW_CHOOSE = 3, 4, 5


class RouteCompareDialog(QDialog):
    """Emits `route_chosen(index)` for the route whose button is pressed, then closes."""

    route_chosen = Signal(int)

    def __init__(self, network: Network, routes: tuple[Route, ...], selected: int, parent=None):
        """Build the table for `routes`; the one at `selected` is the one on screen now."""
        super().__init__(parent)
        self.setWindowTitle(f"Compare routes: {route_title(network, routes[0])}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(560)
        self.routes = routes
        badges = route_badges(list(routes))
        self.table = QTableWidget(ROW_CHOOSE + 1, len(routes))
        self.table.setAccessibleName("Route comparison")
        self.table.setHorizontalHeaderLabels([f"Route {n}" for n in range(1, len(routes) + 1)])
        self.table.setVerticalHeaderLabels([m for m, _ in MEASURES]
                                           + ["Lines used", "Best at", ""])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.buttons: list[QPushButton] = []
        for column, route in enumerate(routes):
            self.fill_column(network, column, route, badges[column])
            self.add_button(column, column == selected)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        self.table.resizeRowsToContents()
        height = (self.table.horizontalHeader().height() + self.table.verticalHeader().length()
                  + 2 * self.table.frameWidth())
        self.table.setFixedHeight(height)  # exactly the rows, no empty space below
        self.resize(max(560, 150 * len(routes) + 130), height + 30)

    def fill_column(self, network: Network, column: int, route: Route,
                    badges: tuple[str, ...]) -> None:
        """The cells of one route; a measure the route wins is bold."""
        values = (f"{minutes(route.total_s)} min", str(len(route.interchanges)),
                  str(route.stops))
        for row, ((_, badge), text) in enumerate(zip(MEASURES, values)):
            self.set_cell(row, column, text, bold=badge in badges)
        self.set_cell(ROW_LINES, column, ", ".join(lines_used(network, route)) or "Walk only")
        self.set_cell(ROW_BEST, column, "; ".join(badges) or "-")

    def set_cell(self, row: int, column: int, text: str, bold: bool = False) -> None:
        """One read-only cell."""
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        self.table.setItem(row, column, item)

    def add_button(self, column: int, showing: bool) -> None:
        """'Choose this route', or a disabled 'Showing now' under the route on screen."""
        button = QPushButton("Showing now" if showing else "Choose this route")
        button.setAccessibleName(f"Choose route {column + 1}")
        button.setEnabled(not showing)
        button.clicked.connect(lambda: self.choose(column))
        self.table.setCellWidget(ROW_CHOOSE, column, button)
        self.buttons.append(button)

    def choose(self, index: int) -> None:
        """Tell the window which route to show, then close."""
        self.route_chosen.emit(index)
        self.close()
