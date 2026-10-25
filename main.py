"""Entry point: load the data, build the graph, open the window (UC9, PRD §6.8).

Usage: python main.py [data-folder]     (default: the data/ folder next to this file)
"""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from metro.console import use_utf8_output
from metro.data import load_network
from metro.errors import DataError, DatasetUnreadable
from metro.graph import build_graph
from metro.ui.main_window import MainWindow

DEFAULT_DATA = Path(__file__).resolve().parent / "data"
LOG_NAME = "metro.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def user_log_folder() -> Path:
    """The per-user folder for the log when the current folder cannot be written to."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "DelhiMetroPlanner"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "DelhiMetroPlanner"
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(state) / "DelhiMetroPlanner"


def setup_logging(candidates: list[Path] | None = None,
                  logger: logging.Logger | None = None) -> Path | None:
    """Log to the first file we can open, else to stderr; return the file used (or None).

    A read-only start folder (an installed copy, a locked-down lab PC) must not stop the app
    from starting, so a failure to open the log is never an error.
    """
    logger = logger or logging.getLogger()
    paths = candidates or [Path(LOG_NAME), user_log_folder() / LOG_NAME]
    handler: logging.Handler = logging.StreamHandler()
    used = None
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, encoding="utf-8")
            used = path
            break
        except OSError:
            continue
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return used


def problems_text(error: Exception, folder: Path) -> str:
    """The start-up dialog text: count, the first 10 problems and the data folder (ER8–ER10)."""
    if isinstance(error, DatasetUnreadable):
        problems = [f"{error.path}: {error.reason}"]
    else:
        problems = error.problems
    lines = [f"The network data has {len(problems)} problem{'s' if len(problems) != 1 else ''}."]
    lines += problems[:10]
    if len(problems) > 10:
        lines.append(f"… and {len(problems) - 10} more (see metro.log).")
    lines.append(f"Data folder: {folder}")
    return "\n".join(lines)


def show_data_error(error: Exception, folder: Path) -> None:
    """Modal start-up error with "Open folder" and "Quit" (the only modal message, [D19])."""
    box = QMessageBox(QMessageBox.Icon.Critical, "Cannot load the network",
                      problems_text(error, folder))
    open_button = box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Quit", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is open_button:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def main(argv: list[str]) -> int:
    """Run the app; returns the process exit code (1 when the data cannot be loaded)."""
    use_utf8_output()
    setup_logging()
    app = QApplication(argv)
    folder = Path(argv[1]) if len(argv) > 1 else DEFAULT_DATA
    splash = QLabel("Loading network…")
    splash.setMinimumSize(240, 60)
    splash.show()
    app.processEvents()
    try:
        network = load_network(folder)
    except (DataError, DatasetUnreadable) as error:
        logging.error("Start-up failed: %s", error)
        if isinstance(error, DataError):
            logging.error("Problems:\n%s", "\n".join(error.problems))
        splash.close()
        show_data_error(error, folder)
        return 1
    window = MainWindow(network, build_graph(network))
    splash.close()
    window.resize(1280, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
