"""Route searches on a background thread (FR15, ER13, ER14, ER17, [D5], [D9], [D32]).

`RouteWorker` lives on one QThread and runs `find_route`. `RouteRunner` lives on the UI
thread and keeps the bookkeeping: the request number that makes old results stale, the
cancel event, the 150 ms "Computing…" timer and the 2 s watchdog.
"""

import logging
import threading

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from metro.app_state import MSG_FAILED, MSG_UNEXPECTED
from metro.errors import RouteCancelled
from metro.router import find_route

log = logging.getLogger(__name__)

COMPUTING_DELAY_MS = 150
WATCHDOG_MS = 2000


class RouteWorker(QObject):
    """Runs searches. Its slot executes on the worker thread, never on the UI thread."""

    finished = Signal(int, object)  # (request_id, Route or None)
    failed = Signal(int, str)  # (request_id, message for the banner)

    def __init__(self, graph, network, find=find_route):
        """`find` is find_route; tests pass a deliberately slow function instead."""
        super().__init__()
        self.graph = graph
        self.network = network
        self.find = find

    @Slot(int, str, str, str, object)
    def compute(self, request_id: int, src: str, dst: str, criterion: str,
                cancel: threading.Event) -> None:
        """Search and report the result tagged with its request number."""
        try:
            route = self.find(self.graph, self.network, src, dst, criterion, cancel)
        except RouteCancelled:
            return  # nobody is waiting for a cancelled search
        except Exception:  # ER17: log the stack trace; the user only sees a short message
            log.exception("Unexpected error while routing %s -> %s", src, dst)
            self.failed.emit(request_id, MSG_UNEXPECTED)
            return
        self.finished.emit(request_id, route)


class RouteRunner(QObject):
    """Starts searches and passes on only the result of the latest one."""

    found = Signal(object)  # Route or None
    failed = Signal(str)
    slow = Signal()  # no result after 150 ms: show "Computing…"
    request = Signal(int, str, str, str, object)  # queued to the worker thread

    def __init__(self, graph, network, find=find_route, watchdog_ms: int = WATCHDOG_MS):
        """Create the worker thread once, at start-up."""
        super().__init__()
        self.request_id = 0
        self.cancel_event: threading.Event | None = None
        self.thread = QThread()
        self.worker = RouteWorker(graph, network, find)
        self.worker.moveToThread(self.thread)
        self.request.connect(self.worker.compute)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.thread.start()
        self.slow_timer = self.single_shot(COMPUTING_DELAY_MS, self.slow.emit)
        self.watchdog = self.single_shot(watchdog_ms, self.on_timeout)

    def single_shot(self, ms: int, callback) -> QTimer:
        """A reusable one-shot timer."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(ms)
        timer.timeout.connect(callback)
        return timer

    def start(self, src: str, dst: str, criterion: str) -> None:
        """New request: number it, cancel the previous one, and send it to the worker."""
        self.cancel()
        self.cancel_event = threading.Event()
        self.slow_timer.start()
        self.watchdog.start()
        self.request.emit(self.request_id, src, dst, criterion, self.cancel_event)

    def cancel(self) -> None:
        """Stop waiting for the current request (Reset, a newer request, or the watchdog)."""
        self.request_id += 1  # any result still on its way is now stale (ER14)
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.slow_timer.stop()
        self.watchdog.stop()

    def is_current(self, request_id: int) -> bool:
        """True for the latest request; stale results are dropped silently (ER14)."""
        if request_id != self.request_id:
            log.info("Discarded stale result for request %d.", request_id)
            return False
        self.slow_timer.stop()
        self.watchdog.stop()
        return True

    def on_finished(self, request_id: int, route) -> None:
        """Pass on the result of the current request."""
        if self.is_current(request_id):
            self.found.emit(route)

    def on_failed(self, request_id: int, message: str) -> None:
        """Pass on an unexpected error of the current request (ER17)."""
        if self.is_current(request_id):
            self.failed.emit(message)

    def on_timeout(self) -> None:
        """Watchdog (ER13): give up on the request and report failure; the UI offers Retry."""
        log.warning("Route calculation timed out.")
        self.cancel()
        self.failed.emit(MSG_FAILED)

    def shutdown(self) -> None:
        """Cancel any search and stop the thread (called when the window closes)."""
        self.cancel()
        self.thread.quit()
        self.thread.wait()
