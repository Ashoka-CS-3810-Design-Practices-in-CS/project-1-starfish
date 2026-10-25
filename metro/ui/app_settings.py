"""Where the app keeps what it remembers between runs (theme, favourite routes)."""

from PySide6.QtCore import QSettings


def app_settings() -> QSettings:
    """The saved preferences, always as an .ini file.

    The native format would be the registry on Windows and a plist on macOS, where tests
    could not redirect it; an .ini file sits in one visible place on every system and
    `QSettings.setPath` can point it at a temporary folder."""
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                     "Starfish", "DelhiMetroPlanner")
