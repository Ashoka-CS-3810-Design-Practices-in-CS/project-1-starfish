"""Start-up helpers: where the log goes and console encoding (Windows robustness)."""

import io
import logging
import sys
import uuid
from pathlib import Path

import pytest
from conftest import REAL_DATA

import main
from metro.console import use_utf8_output


@pytest.fixture
def logger():
    """A private logger, so these tests never touch the root logger's handlers."""
    log = logging.getLogger(f"startup-test-{uuid.uuid4()}")
    log.propagate = False
    yield log
    for handler in log.handlers[:]:
        log.removeHandler(handler)
        handler.close()


def test_log_goes_to_the_first_writable_file(tmp_path, logger):
    """The first candidate is used when it can be opened."""
    first = tmp_path / "metro.log"
    assert main.setup_logging([first, tmp_path / "other.log"], logger) == first
    logger.info("hello")
    logger.handlers[0].flush()
    assert "hello" in first.read_text(encoding="utf-8")
    assert not (tmp_path / "other.log").exists()


def test_unwritable_first_choice_falls_back_to_the_next(tmp_path, logger):
    """A path that is a folder cannot be opened as a file; the next candidate is used."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    fallback = tmp_path / "state" / "metro.log"
    assert main.setup_logging([blocked, fallback], logger) == fallback
    assert fallback.exists()


def test_when_nothing_is_writable_the_log_goes_to_stderr(tmp_path, logger):
    """No file at all still leaves a working logger and no exception."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    assert main.setup_logging([blocked], logger) is None
    # pytest also attaches its own capture handlers to non-propagating loggers, so look at types.
    assert any(type(h) is logging.StreamHandler for h in logger.handlers)
    assert not any(isinstance(h, logging.FileHandler) for h in logger.handlers)


def test_user_log_folder_on_windows_uses_appdata(monkeypatch, tmp_path):
    """On Windows the fallback is %APPDATA%/DelhiMetroPlanner."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert main.user_log_folder() == tmp_path / "DelhiMetroPlanner"


def test_user_log_folder_on_linux_uses_xdg_state(monkeypatch, tmp_path):
    """On Linux the fallback honours XDG_STATE_HOME."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert main.user_log_folder() == tmp_path / "DelhiMetroPlanner"


def cp1252_stream():
    """A text stream like a Windows console in cp1252, and its bytes."""
    raw = io.BytesIO()
    return io.TextIOWrapper(raw, encoding="cp1252", errors="strict", write_through=True), raw


def test_utf8_output_fixes_a_cp1252_console(monkeypatch):
    """Printing → to a cp1252 stream fails; after use_utf8_output it writes UTF-8."""
    stream, raw = cp1252_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    with pytest.raises(UnicodeEncodeError):
        print("→")
    use_utf8_output()
    print("→ ⇒")
    assert raw.getvalue().decode("utf-8").endswith("→ ⇒\n")


def test_utf8_output_ignores_missing_streams(monkeypatch):
    """A windowed build has no stdout or stderr; that is not an error."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    use_utf8_output()


def test_cli_runs_on_a_cp1252_console(monkeypatch):
    """The route CLI no longer crashes when stdout is cp1252."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import route_cli
    stream, raw = cp1252_stream()
    monkeypatch.setattr(sys, "stdout", stream)
    assert route_cli.main(["route_cli.py", str(REAL_DATA), "Rajiv Chowk", "Hauz Khas"]) == 0
    assert "Rajiv Chowk → Hauz Khas" in raw.getvalue().decode("utf-8")
