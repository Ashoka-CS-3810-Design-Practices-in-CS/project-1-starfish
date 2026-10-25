"""Console output that survives a Windows code page (cp1252 cannot print → or ⇒)."""

import sys


def use_utf8_output() -> None:
    """Switch stdout and stderr to UTF-8, replacing anything still unprintable.

    A stream can be missing (a windowed build has no console) or not reconfigurable (a
    replaced stream), and both are fine: then there is nothing to change.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
