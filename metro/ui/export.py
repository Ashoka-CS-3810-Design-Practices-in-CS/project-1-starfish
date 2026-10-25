"""Getting a route out of the app: the clipboard, a text file or a Markdown file (Could tier,
FR18–FR21, ER16, [D57]).

`export_route` never raises for a file problem: it returns a message for the window to show,
so a full disk or a read-only folder cannot lose the route on screen.
"""

import re
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from metro.describe import export_route_text, route_title
from metro.models import Network, Route

FILTERS = {"txt": "Text files (*.txt)", "md": "Markdown files (*.md)"}
# Characters Windows forbids in file names, plus spaces; hyphens are included so that
# "Haat - INA" collapses to "Haat-INA" instead of "Haat---INA".
INVALID_IN_NAMES = re.compile(r'[<>:"/\\|?*\s-]+')


def default_filename(title: str, format: str) -> str:
    """'Rajiv Chowk → Hauz Khas' becomes 'Rajiv-Chowk-to-Hauz-Khas.txt'."""
    stem = INVALID_IN_NAMES.sub("-", title.replace("→", "to")).strip("-") or "route"
    return f"{stem}.{format}"


def ensure_suffix(path: str, format: str) -> str:
    """Add .txt or .md when the user typed a name without any extension."""
    return path if Path(path).suffix else f"{path}.{format}"


def write_export(path: str, text: str) -> str | None:
    """Write the text as UTF-8; None on success, otherwise a message saying why not (ER16)."""
    try:
        Path(path).write_text(text, encoding="utf-8")
    except OSError as error:
        return f"Could not save the route to {path}: {error.strerror or error}."
    return None


def export_route(parent: QWidget, network: Network, route: Route,
                 kind: str) -> tuple[str, str] | None:
    """Export the route; kind is "copy", "txt" or "md".

    Returns ("info" | "error", message) for the window to show, or None if the user
    cancelled the file dialog."""
    format = "md" if kind == "md" else "txt"
    text = export_route_text(network, route, format)
    if kind == "copy":
        QApplication.clipboard().setText(text)
        return "info", "Route copied to the clipboard."
    name = default_filename(route_title(network, route), format)
    path, _ = QFileDialog.getSaveFileName(parent, "Save route", name, FILTERS[format])
    if not path:
        return None
    path = ensure_suffix(path, format)
    error = write_export(path, text)
    return ("error", error) if error else ("info", f"Saved to {path}")
