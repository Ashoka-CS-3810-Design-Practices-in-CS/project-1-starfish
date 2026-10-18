# Viva notes

Running notes for the viva, one section per build step.

## Step 1 — Skeleton, CI, architecture test (M1)

**What was built.** `pyproject.toml` (runtime dependency: PySide6 only; test extras: pytest, pytest-qt, networkx, ruff, pytest-cov), the empty `metro/` and `metro/ui/` packages, a GitHub Actions workflow that lints and tests on Ubuntu, Windows and macOS, and `tests/test_imports.py`.

**Key functions.**
- `core_files()` (`tests/test_imports.py`): lists every `.py` file under `metro/` except those in `metro/ui/`.
- `test_core_never_imports_pyside6()`: reads each core file as text and fails if it contains `import PySide6` or `from PySide6`.
- `test_core_files_exist()`: makes sure the check is not passing just because no files were found.

**Likely questions.**
- *Why check imports with a text search instead of a tool like import-linter?* — It is ten lines, needs no extra tool, and gives the same guarantee for our one rule ([D30]).
- *Why keep Qt out of the core at all?* — The core can then be tested without a display, and the routing logic can be reused by the CLI (`tools/route_cli.py`) unchanged.
- *Why does the slow test only run on Ubuntu?* — It checks all station pairs and is OS-independent pure Python; running it once is enough.
