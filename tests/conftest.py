"""Shared test helpers: fixture paths, one-defect datasets and network variants."""

import json
import random
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from metro.models import Network, TransferOverride

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


def close_stations(network: Network, *station_ids: str) -> Network:
    """A copy of `network` with the given stations marked closed."""
    stations = {sid: replace(st, closed=True) if sid in station_ids else st
                for sid, st in network.stations.items()}
    return replace(network, stations=stations)


def add_override(network: Network, station: str, service_a: str, service_b: str,
                 time_s: int) -> Network:
    """A copy of `network` with one extra transfer override."""
    extra = TransferOverride(station, service_a, service_b, time_s)
    return replace(network, overrides=network.overrides + (extra,))


def shuffled_copy(src: Path, dst: Path, seed: int) -> Path:
    """Copy a dataset with every list of records shuffled (service station order is kept)."""
    rng = random.Random(seed)
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("stations.json", "lines.json", "segments.json"):
        records = json.loads((src / name).read_text())
        rng.shuffle(records)
        (dst / name).write_text(json.dumps(records))
    transfers = json.loads((src / "transfers.json").read_text())
    for key in ("overrides", "no_transfer", "walkways"):
        rng.shuffle(transfers[key])
    (dst / "transfers.json").write_text(json.dumps(transfers))
    return dst
