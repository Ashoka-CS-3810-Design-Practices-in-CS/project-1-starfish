"""A station field with a suggestion list (FR3, FR4, ER2–ER4, [D16], [D20]).

Typing updates up to 8 suggestions. Up/Down move through them, Enter chooses the
highlighted one, and Esc closes the list. Nothing is chosen automatically (T12).
"""

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from metro.describe import station_lines
from metro.models import Network
from metro.search import build_index, is_too_long, search

HINT_COLOUR = "#B3261E"  # dark red: 6.0:1 contrast on white


class SearchBox(QWidget):
    """Emits `station_chosen(id)` when a suggestion is chosen, `cleared()` when the text
    no longer names the chosen station, and `submitted()` for Enter with the list closed."""

    station_chosen = Signal(str)
    cleared = Signal()
    submitted = Signal()

    def __init__(self, label: str, network: Network, parent=None):
        """`label` is "From" or "To"; it is also the field's accessible name."""
        super().__init__(parent)
        self.network = network
        self.index = build_index(network.stations.values())
        self.lines_at = station_lines(network)
        self.chosen: str | None = None
        self.field = QLineEdit()
        self.field.setPlaceholderText(f"{label}: type a station name or code")
        self.field.setClearButtonEnabled(True)
        self.field.setAccessibleName(f"{label} station")
        self.field.installEventFilter(self)
        self.field.textEdited.connect(self.on_text_edited)
        self.field.textChanged.connect(self.on_text_changed)
        self.list = QListWidget()
        self.list.setAccessibleName(f"{label} suggestions")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keyboard stays in the field
        self.list.itemClicked.connect(self.choose_item)
        self.list.hide()
        self.hint = QLabel()
        self.hint.setStyleSheet(f"color: {HINT_COLOUR};")
        self.hint.setWordWrap(True)
        self.hint.setAccessibleName(f"{label} message")
        self.hint.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self.field, self.list, self.hint):
            layout.addWidget(widget)

    # ---- typing and suggestions ---------------------------------------------------------

    def on_text_edited(self, text: str) -> None:
        """The user typed: forget the chosen station and refresh the suggestions."""
        if self.chosen is not None:
            self.chosen = None
            self.cleared.emit()
        self.show_suggestions(text)

    def on_text_changed(self, text: str) -> None:
        """Also catches the clear (x) button, which changes the text without editing it."""
        if not text and self.chosen is not None:
            self.chosen = None
            self.cleared.emit()
        if not text:
            self.close_list()
            self.set_hint(None)

    def show_suggestions(self, text: str) -> None:
        """Fill the list with up to 8 matches, or explain why there are none."""
        matches = search(self.index, text)
        self.list.clear()
        if matches and matches[0].match_type == "FUZZY":
            header = QListWidgetItem("Did you mean …?")
            header.setFlags(Qt.ItemFlag.NoItemFlags)  # a heading, not a choice
            self.list.addItem(header)
        for match in matches:
            self.list.addItem(self.make_item(match))
        self.list.setVisible(bool(matches))
        self.list.setFixedHeight(self.list.sizeHintForRow(0) * self.list.count() + 6
                                 if matches else 0)
        if is_too_long(text):
            self.set_hint("Search text shortened to 100 characters.")  # ER4
        elif text.strip() and not matches:
            self.set_hint(f"No station matches '{text[:40]}'.")  # ER2
        else:
            self.set_hint(None)

    def make_item(self, match) -> QListWidgetItem:
        """One suggestion: the name plus its lines in words; closed stations dimmed."""
        lines = ", ".join(self.lines_at[match.station_id]) or "no line"
        text = f"{match.name} · {lines}"
        item = QListWidgetItem(text + (" · closed" if match.closed else ""))
        item.setData(Qt.ItemDataRole.UserRole, match.station_id)
        item.setToolTip(f"{match.name} ({match.station_id}) — {lines}")
        if match.closed:
            item.setForeground(QColor("#6B6B6B"))
        return item

    def set_hint(self, text: str | None) -> None:
        """Show or hide the message under the field."""
        self.hint.setText(text or "")
        self.hint.setVisible(bool(text))

    # ---- choosing --------------------------------------------------------------------------

    def choose_item(self, item: QListWidgetItem) -> None:
        """Choose a suggestion: show the canonical name and announce the station."""
        station_id = item.data(Qt.ItemDataRole.UserRole)
        if station_id is None:
            return  # the "Did you mean" heading
        self.set_station(station_id)
        self.station_chosen.emit(station_id)

    def set_station(self, station_id: str | None) -> None:
        """Show a station chosen elsewhere (map click, swap, reset) without re-emitting."""
        self.chosen = station_id
        self.field.blockSignals(True)
        self.field.setText(self.network.stations[station_id].name if station_id else "")
        self.field.blockSignals(False)
        self.close_list()
        self.set_hint(None)

    def close_list(self) -> None:
        """Hide the suggestion list."""
        self.list.clear()
        self.list.hide()

    def list_is_open(self) -> bool:
        """True while suggestions are showing (then Esc closes the list, not Reset)."""
        return self.list.isVisible() and self.list.count() > 0

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Up/Down/Enter/Esc in the field drive the suggestion list."""
        if obj is not self.field or event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.list_is_open():
            self.move_highlight(1 if key == Qt.Key.Key_Down else -1)
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.list_is_open() and self.list.currentItem() is not None:
                self.choose_item(self.list.currentItem())
            elif self.chosen is not None:
                self.submitted.emit()
            return True
        if key == Qt.Key.Key_Escape and self.list_is_open():
            self.close_list()
            return True
        return super().eventFilter(obj, event)

    def move_highlight(self, step: int) -> None:
        """Move the highlighted row, skipping the non-selectable heading."""
        row = self.list.currentRow() + step
        while 0 <= row < self.list.count():
            if self.list.item(row).flags() & Qt.ItemFlag.ItemIsEnabled:
                self.list.setCurrentRow(row)
                return
            row += step
