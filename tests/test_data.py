"""Tests for loading and validation (A2 Alg. 1; FR1, ER8–ER10; T17, T18)."""

import logging
import shutil

import pytest
from conftest import TOY_BRANCH_LOOP, TOY_METRO

from metro.data import has_kind, load_network
from metro.errors import DataError, DatasetUnreadable
from metro.validate import consecutive_pairs, is_connected


def problems_of(folder) -> list[str]:
    """Load `folder`, expecting a DataError, and return its problem list."""
    with pytest.raises(DataError) as info:
        load_network(folder)
    return info.value.problems


# ---- valid fixtures ----------------------------------------------------------------


def test_toy_metro_loads():
    """The toy_metro fixture is valid and has the expected contents."""
    net = load_network(TOY_METRO)
    assert list(net.stations) == ["A", "B", "C", "D", "E", "F", "H", "I"]
    assert list(net.lines) == ["BLUE", "GREEN", "RED", "YELLOW"]
    assert list(net.services) == ["B1", "G1", "R1", "Y1"]
    assert net.services["R1"].stations == ("A", "B", "C", "D")
    assert net.default_other_line_s == 240
    assert len(net.segments) == 7 and len(net.walkways) == 1


def test_toy_branch_loop_loads():
    """The branch/loop fixture is valid; V is a loop and O1, O2 share the Orange line."""
    net = load_network(TOY_BRANCH_LOOP)
    assert net.services["V"].loop is True
    assert net.services["O1"].line_id == net.services["O2"].line_id == "ORANGE"


# ---- T17: each one-defect fixture is rejected with exactly one precise message --------

ONE_DEFECT = [
    ("missing_field", "stations.json, entry I, field lat: missing"),
    ("wrong_type", "stations.json, entry A, field closed: expected bool"),
    ("duplicate_id", "stations.json, entry A, field id: duplicate ID"),
    ("unknown_station", "transfers.json, entry W-02, field b: unknown station Q"),
    ("time_too_small", "segments.json, entry S-01, field time_s: 5 (min 10)"),
    ("time_too_large", "segments.json, entry S-01, field time_s: 601 (max 600)"),
    ("missing_segment", "lines.json, entry R1, field stations: no RED segment between C and D"),
    ("unused_segment", "segments.json, entry S-08, field a/b: segment is used by no service"),
    ("orphan_station", "stations.json, entry Z: station is on no service and in no walkway"),
    ("bad_coordinates", "stations.json, entry A, field lat/lon: (30.0, 77.1) "
                        "is outside the NCR box"),
    ("bad_override", "transfers.json, entry override #0, field service_b: "
                     "service B1 does not serve A"),
]


@pytest.mark.parametrize("name, message", ONE_DEFECT)
def test_t17_one_defect_fixture_is_rejected(broken_dataset, name, message):
    """T17: each single defect produces exactly one problem with file, entry and field."""
    assert problems_of(broken_dataset(name)) == [message]


def test_t18_multi_defect_reports_every_problem(broken_dataset):
    """T18: four independent defects give four problems, not just the first."""
    problems = problems_of(broken_dataset("multi_defect"))
    assert len(problems) == 4
    assert any("field lat/lon" in p for p in problems)
    assert any("time_s: 5 (min 10)" in p for p in problems)
    assert any("entry Z: station is on no service" in p for p in problems)
    assert any("unknown station Q" in p for p in problems)


def test_data_error_message_counts_problems(broken_dataset):
    """The exception text gives the count the start-up dialog shows (ER9)."""
    with pytest.raises(DataError, match="has 4 problems"):
        load_network(broken_dataset("multi_defect"))


# ---- unreadable data (ER8) and warnings (check 11) ----------------------------------


def test_invalid_json_is_unreadable(broken_dataset):
    """A syntax error raises DatasetUnreadable naming the file."""
    with pytest.raises(DatasetUnreadable) as info:
        load_network(broken_dataset("invalid_json"))
    assert info.value.path.endswith("lines.json")
    assert "not valid JSON" in info.value.reason


def test_missing_file_is_unreadable(broken_dataset):
    """A missing file raises DatasetUnreadable."""
    folder = broken_dataset("disconnected")
    (folder / "segments.json").unlink()
    with pytest.raises(DatasetUnreadable, match="file not found"):
        load_network(folder)


def test_disconnected_network_is_only_a_warning(broken_dataset, caplog):
    """Without the D-H walkway, H and I are cut off: loading works but logs a warning."""
    with caplog.at_level(logging.WARNING):
        net = load_network(broken_dataset("disconnected"))
    assert net.walkways == ()
    assert "disconnected" in caplog.text


def test_wrong_top_level_type(broken_dataset):
    """A file whose top level is not a list is reported, not crashed on."""
    folder = broken_dataset("disconnected")
    (folder / "segments.json").write_text('{"oops": 1}')
    problems = problems_of(folder)
    assert "segments.json: expected a list at the top level" in problems


# ---- small helpers -------------------------------------------------------------------


def test_time_bounds_are_inclusive(tmp_path):
    """10 s and 600 s are accepted; only values outside them are errors (check 5)."""
    shutil.copytree(TOY_METRO, tmp_path / "toy")
    path = tmp_path / "toy" / "segments.json"
    text = path.read_text().replace('"time_s": 120', '"time_s": 10', 1)
    path.write_text(text.replace('"time_s": 180', '"time_s": 600', 1))
    net = load_network(tmp_path / "toy")
    assert {s.time_s for s in net.segments} >= {10, 600}


def test_has_kind_treats_bool_separately():
    """A JSON true is not an int, and an int is a valid number."""
    assert not has_kind(True, "int")
    assert has_kind(True, "bool")
    assert has_kind(3, "number") and has_kind(3.5, "number")
    assert has_kind(["a"], "list[str]") and not has_kind(["a", 1], "list[str]")


def test_consecutive_pairs_adds_closing_pair_for_loops():
    """A loop service also runs from its last station back to its first."""
    assert consecutive_pairs(("C", "L2", "L3"), loop=False) == [("C", "L2"), ("L2", "L3")]
    assert consecutive_pairs(("C", "L2", "L3"), loop=True)[-1] == ("L3", "C")


def test_is_connected_on_toy_fixtures():
    """Both toy fixtures are connected (toy_metro only through the D-H walkway)."""
    assert is_connected(load_network(TOY_METRO))
    assert is_connected(load_network(TOY_BRANCH_LOOP))
