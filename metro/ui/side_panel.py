"""The left column of the window: search, controls, message banner and the route (FR3–FR8,
FR13, FR14, [D20]). It builds the widgets and lays them out; the window connects them."""

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from metro.describe import CRITERION_LABELS
from metro.models import Network
from metro.ui.route_panel import Banner, RoutePanel
from metro.ui.search_box import SearchBox

CRITERIA = [(text, key) for key, text in CRITERION_LABELS.items()]
PANEL_WIDTH = 380


class SidePanel(QWidget):
    """From and To boxes, criterion, Find/Swap/Reset, banner and the route panel."""

    def __init__(self, network: Network, parent=None):
        """Create every widget with an accessible name and place it top to bottom."""
        super().__init__(parent)
        self.setFixedWidth(PANEL_WIDTH)
        self.from_box = SearchBox("From", network)
        self.to_box = SearchBox("To", network)
        self.criterion = QComboBox()
        for text, value in CRITERIA:
            self.criterion.addItem(text, value)
        self.criterion.setAccessibleName("Criterion")
        self.find_button = QPushButton("Find route")
        self.swap_button = QPushButton("Swap")
        self.reset_button = QPushButton("Reset (Esc)")
        for button, name in ((self.find_button, "Find route"), (self.swap_button, "Swap"),
                             (self.reset_button, "Reset")):
            button.setAccessibleName(name)
        self.swap_button.setToolTip("Swap From and To (Alt+W)")
        self.banner = Banner()
        self.route_panel = RoutePanel(network)
        self.layout_widgets()

    def layout_widgets(self) -> None:
        """Hint, fields, criterion row, buttons, banner, then the route filling the rest."""
        side = QVBoxLayout(self)
        hint = QLabel("Type a station or click the map: first click sets From, second sets "
                      "To, a third click starts again.")
        hint.setWordWrap(True)
        criterion_row = QHBoxLayout()
        criterion_row.addWidget(QLabel("Criterion"))
        criterion_row.addWidget(self.criterion, 1)
        buttons = QHBoxLayout()
        for button in (self.find_button, self.swap_button, self.reset_button):
            buttons.addWidget(button)
        side.addWidget(hint)
        side.addWidget(self.from_box)
        side.addWidget(self.to_box)
        side.addLayout(criterion_row)
        side.addLayout(buttons)
        side.addWidget(self.banner)
        side.addWidget(self.route_panel, 1)

    def tab_chain(self) -> list[QWidget]:
        """The widgets in keyboard order, top to bottom."""
        return [self.from_box.field, self.to_box.field, self.criterion, self.find_button,
                self.swap_button, self.reset_button, self.route_panel.rows]
