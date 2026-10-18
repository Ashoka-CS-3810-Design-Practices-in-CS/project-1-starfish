"""The few exception types the core raises (PRD §8).

No-route is not an exception: `find_route` returns None (ER7).
Same-station and closed-station inputs are handled in `app_state`.
"""


class MetroError(Exception):
    """Base class for every error raised by the core."""


class DatasetUnreadable(MetroError):
    """A data file is missing, unreadable or not valid JSON (ER8)."""

    def __init__(self, path: str, reason: str):
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class DataError(MetroError):
    """The data was readable but has problems; lists every one of them (ER9, ER10)."""

    def __init__(self, problems: list[str]):
        super().__init__(f"The network data has {len(problems)} problems.")
        self.problems = problems


class RouteCancelled(MetroError):
    """A route search was cancelled by the watchdog or by a newer request ([D5])."""
