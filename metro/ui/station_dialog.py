"""The station card: what a station is and quick ways to use it (Could tier, [D54]).

Opened from the map's right-click menu or with Ctrl+I. Not modal: the map stays usable.
Line names are written in words as well as shown in the line's colour, so colour is never
the only cue ([D20]).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from metro.describe import station_details
from metro.models import Network
from metro.ui.theme import contrast_ratio, luminance  # noqa: F401  (luminance re-exported)


def text_colour_on(background: str) -> str:
    """Black or white, whichever has the higher contrast ratio on `background`."""
    return "#000000" if contrast_ratio(background, "#000000") >= \
        contrast_ratio(background, "#FFFFFF") else "#FFFFFF"


class StationDialog(QDialog):
    """Shows one station. Emits `set_as_from(id)` or `set_as_to(id)` and then closes."""

    set_as_from = Signal(str)
    set_as_to = Signal(str)

    def __init__(self, network: Network, station_id: str, parent=None):
        """Build the card from `station_details`."""
        super().__init__(parent)
        self.station_id = station_id
        details = station_details(network, station_id)
        self.setWindowTitle(f"Station details: {details.name}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(self)
        self.title = QLabel(details.name)
        font = self.title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 3)
        self.title.setFont(font)
        self.title.setAccessibleName("Station name")
        layout.addWidget(self.title)
        layout.addWidget(self.fact(f"Code: {details.id}", "Station code"))
        if details.aliases:
            layout.addWidget(self.fact("Also known as: " + ", ".join(details.aliases), "Aliases"))
        layout.addWidget(self.line_tags(details.lines))
        if details.interchange_note:
            layout.addWidget(self.fact(details.interchange_note, "Interchange"))
        if details.terminal_of:
            layout.addWidget(self.fact("Terminal station of: " + ", ".join(details.terminal_of),
                                       "Terminal"))
        if details.neighbours:
            layout.addWidget(self.fact("Next to: " + ", ".join(details.neighbours), "Neighbours"))
        layout.addWidget(self.fact(f"Position: {details.coordinates}", "Coordinates"))
        if details.closed:
            layout.addWidget(self.fact("This station is closed.", "Closed"))
        layout.addLayout(self.buttons(details.closed))

    def fact(self, text: str, name: str) -> QLabel:
        """One wrapped line of text with an accessible name."""
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAccessibleName(name)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def line_tags(self, lines: tuple[tuple[str, str], ...]) -> QWidget:
        """A row of coloured tags, one per line, each with the line's name as text."""
        row = QWidget()
        row.setAccessibleName("Lines")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tags = []
        for name, colour in lines or ((("No line"), "#DDDDDD"),):
            tag = QLabel(name)
            tag.setStyleSheet(f"background: {colour}; color: {text_colour_on(colour)}; "
                              "border-radius: 4px; padding: 2px 8px;")
            tag.setAccessibleName(f"Line: {name}")
            layout.addWidget(tag)
            self.tags.append(tag)
        layout.addStretch(1)
        return row

    def buttons(self, closed: bool) -> QHBoxLayout:
        """Set as From, Set as To (off for a closed station, ER6) and Close."""
        row = QHBoxLayout()
        self.from_button = QPushButton("Set as From")
        self.to_button = QPushButton("Set as To")
        close = QPushButton("Close")
        for button in (self.from_button, self.to_button, close):
            button.setAccessibleName(button.text())
            row.addWidget(button)
        for button in (self.from_button, self.to_button):
            button.setEnabled(not closed)
            button.setToolTip("A closed station cannot be used." if closed else "")
        self.from_button.clicked.connect(lambda: self.choose(self.set_as_from))
        self.to_button.clicked.connect(lambda: self.choose(self.set_as_to))
        close.clicked.connect(self.close)
        return row

    def choose(self, signal: Signal) -> None:
        """Pass the station on and close the card."""
        signal.emit(self.station_id)
        self.close()
