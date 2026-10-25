"""Buttons floating on the corner of the map (Should/Could tier, [D20], [D51], [D55]).

Mouse users who have no wheel or never learn the + / - / 0 keys get visible controls.
The buttons never take keyboard focus by click, so the map keeps its key shortcuts.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget

BUTTON_PX = 36


class MapControls(QWidget):
    """A column of buttons; each emits a signal and knows nothing about the map."""

    zoom_in = Signal()
    zoom_out = Signal()
    fit = Signal()
    theme_toggled = Signal()

    def __init__(self, parent=None):
        """Build the column: zoom in, zoom out, fit."""
        super().__init__(parent)
        self.setObjectName("mapControls")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.zoom_in_button = self.add_button(layout, "+", "Zoom in", "Zoom in (+)", self.zoom_in)
        self.zoom_out_button = self.add_button(layout, "−", "Zoom out", "Zoom out (-)",
                                               self.zoom_out)
        self.fit_button = self.add_button(layout, "Fit", "Fit the whole network",
                                          "Show the whole network (0)", self.fit)
        self.theme_button = self.add_button(layout, "◐", "Switch theme", "Switch theme",
                                            self.theme_toggled)
        self.adjustSize()

    def show_theme(self, next_name: str) -> None:
        """Say what the theme button will switch to ("dark" or "light")."""
        self.theme_button.setAccessibleName(f"Switch to {next_name} theme")
        self.theme_button.setToolTip(f"Switch to the {next_name} theme")

    def add_button(self, layout: QVBoxLayout, text: str, name: str, tip: str,
                   signal: Signal) -> QToolButton:
        """One square button with an accessible name and a tooltip."""
        button = QToolButton()
        button.setText(text)
        button.setAccessibleName(name)
        button.setToolTip(tip)
        button.setFixedSize(BUTTON_PX, BUTTON_PX)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        button.clicked.connect(signal)
        layout.addWidget(button)
        return button
