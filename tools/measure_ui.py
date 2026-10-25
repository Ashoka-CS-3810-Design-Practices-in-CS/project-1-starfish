"""Measure what docs/performance.md reports about the window: memory and drawing time.

Usage: python tools/measure_ui.py [data-folder]

Set QT_QPA_PLATFORM=offscreen to run without opening a window (the numbers then leave out
the desktop's own window system, so compare like with like). Memory is the resident size from
`ps`, so it is printed on macOS and Linux only; on Windows read it in Task Manager.
Drawing time is how long one repaint of the map takes (`viewport().grab()`), a stand-in for
the frame time: the 60 frames per second target needs a median of 16.7 ms or less.
"""

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metro.data import load_network  # noqa: E402
from metro.graph import build_graph  # noqa: E402
from metro.ui.main_window import MainWindow  # noqa: E402

REPEATS = 100
SETTLE_S = 1.0


def rss_mb() -> float | None:
    """Resident memory of this process in MB, or None where `ps` does not exist."""
    if sys.platform == "win32":
        return None
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                         capture_output=True, text=True).stdout.strip()
    return int(out) / 1024 if out else None


def settle(app: QApplication, seconds: float = SETTLE_S) -> None:
    """Let Qt finish layout, paint and the worker thread."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def timings_ms(action, repeats: int = REPEATS) -> tuple[float, float]:
    """(median, 95th percentile) in milliseconds of `repeats` calls."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        action()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples), statistics.quantiles(samples, n=20)[-1]


def show_memory(label: str) -> None:
    """Print one memory line."""
    value = rss_mb()
    print(f"{label:<44} {'n/a (use Task Manager)' if value is None else f'{value:6.0f} MB'}")


def main(argv: list[str]) -> int:
    """Run every measurement and print a table."""
    folder = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / "data"
    app = QApplication([])
    print(f"Platform: {QApplication.platformName()}, Python {sys.version.split()[0]}\n")
    show_memory("after QApplication, nothing shown")
    bare = QWidget()
    bare.resize(1280, 800)
    bare.show()
    settle(app, 0.5)
    show_memory("bare empty QWidget 1280x800")
    bare.close()
    network = load_network(folder)
    window = MainWindow(network, build_graph(network))
    window.resize(1280, 800)
    window.show()
    settle(app)
    show_memory("planner window, no route")
    by_name = {s.name: i for i, s in network.stations.items()}
    window.on_map_click(by_name["Samaypur Badli"])
    window.on_map_click(by_name["Noida City Centre"])
    settle(app)
    show_memory("planner window, route shown")
    print(f"\nRoute: {window.route_panel.summary.text()}\n")
    view = window.map
    grab = view.viewport().grab
    print(f"{'drawing one frame of the map':<44} {'median':>8} {'p95':>8}")
    rows = [("fitted to the route", grab)]
    rows.append(("zoomed out, whole network", lambda: (view.fit_all(), grab())[1]))
    view.zoom_by(4)
    rows.append(("zoomed in 4x (labels on)", grab))
    view.animator.play()
    rows.append(("animation tick + frame", lambda: (view.animator.advance(16), grab())[1]))
    for label, action in rows:
        median, p95 = timings_ms(action)
        print(f"{label:<44} {median:7.1f}ms {p95:7.1f}ms")
    view.animator.pause()
    median, p95 = timings_ms(lambda: (view.zoom_by(1.15), view.zoom_by(1 / 1.15)), 50)
    print(f"{'one zoom step incl. label overlap test':<44} {median / 2:7.1f}ms {p95 / 2:7.1f}ms")
    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
