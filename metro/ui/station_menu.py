"""The right-click menu of a station on the map ([D54])."""

from PySide6.QtWidgets import QMenu, QWidget

from metro.models import Network

ACTIONS = (("Station details…", "details"), ("Set as From", "from"), ("Set as To", "to"))


def build_station_menu(parent: QWidget, network: Network, station_ids: list[str],
                       emit) -> QMenu:
    """Details / Set as From / Set as To for one station; a submenu per station where several
    overlap, so a cluster can still be used. `emit(action, station_id)` is called on a pick."""
    menu = QMenu(parent)
    for sid in station_ids:
        name = network.stations[sid].name
        target = menu if len(station_ids) == 1 else menu.addMenu(name)
        for text, action in ACTIONS:
            target.addAction(text, lambda a=action, s=sid: emit(a, s))
    return menu
