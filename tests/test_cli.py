"""Tests for the command-line walking skeleton and the shared route text (tools/route_cli.py)."""

import sys
from pathlib import Path

from conftest import REAL_DATA, TOY_METRO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import route_cli  # noqa: E402  (tools/ is a folder of scripts, not a package)


def test_cli_prints_a_route(capsys):
    """The PRD's example command prints the summary and one Yellow leg."""
    assert route_cli.main(["route_cli.py", str(REAL_DATA), "Rajiv Chowk", "Hauz Khas"]) == 0
    out = capsys.readouterr().out
    assert "Rajiv Chowk → Hauz Khas" in out
    assert "0 interchanges" in out and "Yellow Line towards" in out


def test_cli_prints_interchange_and_walk_lines(capsys):
    """A walk interchange is described as 'Walk from X to Y'."""
    assert route_cli.main(["route_cli.py", str(TOY_METRO), "A", "I"]) == 0
    out = capsys.readouterr().out
    assert "Estimated 15 min · 1 interchange · 4 stops" in out
    assert "⇒ Walk from Station D to Station H (5 min)" in out


def test_cli_suggests_on_inexact_name(capsys):
    """A typo is not routed; suggestions are printed instead."""
    assert route_cli.main(["route_cli.py", str(REAL_DATA), "rajib chowk", "Hauz Khas"]) == 1
    assert "Did you mean: Rajiv Chowk?" in capsys.readouterr().out


def test_cli_reports_no_route(capsys, broken_dataset):
    """Without the D-H walkway, H cannot reach A: the ER7 message is printed."""
    folder = broken_dataset("disconnected")
    assert route_cli.main(["route_cli.py", str(folder), "H", "A"]) == 1
    assert "No route found between Station H and Station A" in capsys.readouterr().out


def test_cli_usage_on_bad_arguments(capsys):
    """Wrong argument count prints usage and returns 2."""
    assert route_cli.main(["route_cli.py"]) == 2
    assert "Usage" in capsys.readouterr().out


def test_station_tooltip_text():
    """Tooltips show name, code, lines and badges; one line means no interchange badge."""
    from metro.data import load_network
    from metro.describe import station_lines, station_tooltip
    net = load_network(TOY_METRO)
    lines = station_lines(net)
    assert lines["C"] == ["Blue Line", "Red Line"]
    assert station_tooltip(net, "C", lines["C"]) == \
        "Station C (C)\nBlue Line, Red Line\nInterchange"
    assert station_tooltip(net, "A", lines["A"]) == "Station A (A)\nRed Line"


def test_cli_stations_flag_lists_intermediate_stations(capsys):
    """--stations works in any position and adds one row per station passed through."""
    args = ["route_cli.py", "--stations", str(REAL_DATA), "Rajiv Chowk", "Hauz Khas"]
    assert route_cli.main(args) == 0
    out = capsys.readouterr().out
    rows = [line for line in out.splitlines() if line.startswith("     · ")]
    assert len(rows) == 8  # Rajiv Chowk -> Hauz Khas is 9 stops, so 8 stations in between
    assert route_cli.main(args[:1] + args[2:]) == 0
    assert "     · " not in capsys.readouterr().out
