"""Architecture test (PRD §9.6): the core package must not depend on Qt."""

from pathlib import Path

METRO = Path(__file__).resolve().parent.parent / "metro"


def core_files() -> list[Path]:
    """Every .py file in metro/ that is outside metro/ui/."""
    ui = METRO / "ui"
    return [p for p in METRO.rglob("*.py") if ui not in p.parents]


def test_core_files_exist():
    """Guard against the check passing vacuously because the glob found nothing."""
    assert core_files()


def test_core_never_imports_pyside6():
    """No core file may contain `import PySide6` or `from PySide6`."""
    offenders = []
    for path in core_files():
        text = path.read_text(encoding="utf-8")
        if "import PySide6" in text or "from PySide6" in text:
            offenders.append(path.name)
    assert offenders == []
