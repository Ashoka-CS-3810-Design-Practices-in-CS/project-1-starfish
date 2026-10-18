"""Shared test helpers: fixture paths and a way to build one-defect datasets."""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOY_METRO = FIXTURES / "toy_metro"
TOY_BRANCH_LOOP = FIXTURES / "toy_branch_loop"
BROKEN = FIXTURES / "broken"
REAL_DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def broken_dataset(tmp_path):
    """Return a function that builds toy_metro with one broken/<name>/ folder laid over it.

    Each broken folder holds only the files that differ from toy_metro.
    """
    def build(name: str) -> Path:
        folder = tmp_path / name
        shutil.copytree(TOY_METRO, folder)
        for path in (BROKEN / name).iterdir():
            shutil.copy(path, folder / path.name)
        return folder
    return build
