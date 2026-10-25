"""Tests for the favourites list: round trip, damaged saves and the size cap."""

import json

import pytest
from conftest import TOY_METRO

from metro.data import load_network
from metro.favorites import MAX_FAVORITES, Favorite, decode, encode, label, toggle


@pytest.fixture(scope="module")
def net():
    """toy_metro (stations A–F, H, I)."""
    return load_network(TOY_METRO)


def test_round_trip(net):
    """What is encoded decodes to the same list in the same order."""
    favorites = (Favorite("A", "F"), Favorite("D", "I", "fewest_stops"))
    assert decode(encode(favorites), net) == favorites


@pytest.mark.parametrize("text", ["", "not json", "{}", "42", "null", "[1, 2]", "[[]]"])
def test_damaged_text_gives_an_empty_list(net, text):
    """ER15: nothing unreadable raises."""
    assert decode(text, net) == ()


def test_decode_none_is_safe(net):
    """A missing QSettings value may arrive as None."""
    assert decode(None, net) == ()


def test_invalid_entries_are_dropped_and_valid_ones_kept(net):
    """Unknown station, same station, bad criterion, wrong types and duplicates are removed."""
    entries = [
        {"from": "A", "to": "F"},  # valid, criterion defaults to fastest
        {"from": "A", "to": "ZZZ"},  # unknown station
        {"from": "C", "to": "C"},  # same station
        {"from": "A", "to": "F", "criterion": "scenic"},  # unknown criterion
        {"from": 1, "to": "F"},  # wrong type
        {"from": "A", "to": "F", "criterion": "fastest"},  # duplicate of the first
        {"from": "B", "to": "E", "criterion": "fewest_changes"},
    ]
    assert decode(json.dumps(entries), net) == (Favorite("A", "F"),
                                                Favorite("B", "E", "fewest_changes"))


def test_toggle_adds_at_the_front_then_removes(net):
    """The first toggle saves (newest first); the second removes."""
    first, second = Favorite("A", "F"), Favorite("D", "I")
    saved = toggle(toggle((), first), second)
    assert saved == (second, first)
    assert toggle(saved, first) == (second,)


def test_the_list_is_capped_and_keeps_the_newest():
    """Saving more than MAX_FAVORITES drops the oldest."""
    saved = ()
    for i in range(MAX_FAVORITES + 5):
        saved = toggle(saved, Favorite(f"S{i}", "X"))
    assert len(saved) == MAX_FAVORITES
    assert saved[0] == Favorite(f"S{MAX_FAVORITES + 4}", "X")


def test_label_names_stations_and_criterion(net):
    """The menu text uses display names, not codes."""
    assert label(net, Favorite("A", "F", "fewest_stops")) == \
        "Station A → Station F · Fewest stops"
