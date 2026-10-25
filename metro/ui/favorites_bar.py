"""A star to save the route on screen and a menu to bring saved routes back (Could tier,
FR18–FR21, ER15, [D48]).

All list logic is in `metro.favorites`; this widget only shows it and keeps it in QSettings.
"""

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QToolButton, QWidget

from metro import favorites as fav
from metro.favorites import Favorite
from metro.models import Network

SETTINGS_KEY = "favorites"


class FavoritesBar(QWidget):
    """Emits `chosen(source, destination, criterion)` when a saved route is picked."""

    chosen = Signal(str, str, str)

    def __init__(self, network: Network, settings: QSettings, parent=None):
        """Load the saved list; a damaged saved value just gives an empty list (ER15)."""
        super().__init__(parent)
        self.network = network
        self.settings = settings
        self.saved = fav.decode(settings.value(SETTINGS_KEY), network)
        self.journey: Favorite | None = None  # the route on screen, if any
        self.star = QPushButton()
        self.star.clicked.connect(self.toggle)
        self.menu_button = QToolButton()
        self.menu_button.setText("Favourites")
        self.menu_button.setAccessibleName("Favourite routes")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self.menu_button)
        self.menu_button.setMenu(self.menu)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.star, 1)
        layout.addWidget(self.menu_button)
        self.refresh()

    def set_journey(self, journey: Favorite | None) -> None:
        """Tell the bar which route is on screen (None for none) and update the star."""
        self.journey = journey
        self.refresh()

    def toggle(self) -> None:
        """Save the route on screen, or remove it if it is already saved."""
        if self.journey is None:
            return
        self.saved = fav.toggle(self.saved, self.journey)
        self.settings.setValue(SETTINGS_KEY, fav.encode(self.saved))
        self.settings.sync()
        self.refresh()

    def remove(self, favorite: Favorite) -> None:
        """Remove one saved route (from the menu), whether or not it is on screen."""
        self.saved = tuple(f for f in self.saved if f != favorite)
        self.settings.setValue(SETTINGS_KEY, fav.encode(self.saved))
        self.settings.sync()
        self.refresh()

    def refresh(self) -> None:
        """Star text and state from the journey; the menu from the saved list."""
        saved = self.journey is not None and self.journey in self.saved
        self.star.setEnabled(self.journey is not None)
        self.star.setText("★ Saved - click to remove" if saved else "☆ Add to favourites")
        self.star.setAccessibleName("Remove from favourites" if saved else "Add to favourites")
        self.star.setToolTip("" if self.journey else "Find a route first.")
        self.menu.clear()
        if not self.saved:
            self.menu.addAction("No favourites yet").setEnabled(False)
            return
        for favorite in self.saved:
            self.menu.addAction(fav.label(self.network, favorite),
                                lambda f=favorite: self.chosen.emit(f.source, f.destination,
                                                                    f.criterion))
        remove = self.menu.addMenu("Remove")
        for favorite in self.saved:
            remove.addAction(fav.label(self.network, favorite), lambda f=favorite: self.remove(f))
