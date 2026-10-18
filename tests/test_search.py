"""Station search tests (A2 Alg. 5 simplified; FR3, ER2–ER4, [D16], [D26]; T11–T14)."""

import random

from metro.models import Station
from metro.search import (
    build_index,
    fuzzy_limit,
    is_too_long,
    levenshtein_within,
    normalise,
    search,
)


def station(sid, name, aliases=(), closed=False):
    """A station with dummy coordinates (search never looks at them)."""
    return Station(sid, name, 28.6, 77.2, tuple(aliases), closed)


STATIONS = [
    station("RJCK", "Rajiv Chowk", ["CP", "Connaught Place"]),
    station("RJGN", "Rajouri Garden"),
    station("HZKS", "Hauz Khas"),
    station("KSHG", "Kashmere Gate"),
    station("NDLS", "New Delhi"),
    station("NSPL", "Netaji Subhash Place"),
    station("SC18", "Noida Sector 18"),
    station("SC15", "Noida Sector 15"),
    station("MDTN", "Model Town", closed=True),
    station("JNPW", "Janakpuri West"),
    station("JNPE", "Janakpuri East"),
    station("CP", "Chandni Point"),  # a code equal to another station's alias
]
INDEX = build_index(STATIONS)


def ids(query):
    """Station IDs returned for a query, best first."""
    return [m.station_id for m in search(INDEX, query)]


# ---- T11: exact matches and ranking ---------------------------------------------------


def test_t11_exact_name_ranks_first():
    """T11: an exact name beats prefix and substring matches."""
    results = search(INDEX, "Hauz Khas")
    assert (results[0].station_id, results[0].match_type) == ("HZKS", "NAME")


def test_t11_code_beats_alias():
    """T11: CODE (rank 0) beats an alias NAME match (rank 1) for the same text."""
    results = search(INDEX, "cp")
    assert [(m.station_id, m.match_type) for m in results[:2]] == \
        [("CP", "CODE"), ("RJCK", "NAME")]


def test_t11_ranking_order_prefix_then_substring():
    """T11: PREFIX before SUBSTRING; equal rank sorts by name."""
    results = search(INDEX, "janakpuri")
    assert [m.station_id for m in results] == ["JNPE", "JNPW"]
    assert {m.match_type for m in results} == {"PREFIX"}
    assert ids("west") == ["JNPW"]
    assert search(INDEX, "west")[0].match_type == "SUBSTRING"


# ---- T12: ambiguous input lists every candidate, nothing is chosen automatically -------


def test_t12_ambiguous_prefix_lists_all_candidates():
    """T12: "raj" lists both Rajiv Chowk and Rajouri Garden; the caller must choose."""
    assert ids("raj") == ["RJCK", "RJGN"]


def test_t12_results_capped_at_eight():
    """At most 8 suggestions are returned."""
    many = build_index([station(f"S{i:02}", f"Sample {i:02}") for i in range(20)])
    assert len(search(many, "sample")) == 8


# ---- T13: codes, aliases, normalisation -------------------------------------------------


def test_t13_code_and_alias_lookup():
    """T13: a station code and an alias each find the station."""
    assert ids("KSHG")[0] == "KSHG"
    assert ids("connaught place")[0] == "RJCK"


def test_t13_sec_expands_to_sector():
    """T13: "sec 18" means "sector 18"."""
    assert ids("noida sec 18")[0] == "SC18"
    assert normalise("Sec  18") == "sector 18"
    assert normalise("second") == "second"  # only the whole word is expanded


def test_t13_normalise_steps():
    """NFKC, control characters, case and whitespace are all normalised."""
    assert normalise("  ＲＡＪＩＶ\tChowk\x00 ") == "rajiv chowk"
    assert normalise("") == ""


def test_closed_station_is_listed_with_flag():
    """Closed stations still appear, flagged, so the UI can dim them."""
    (match,) = search(INDEX, "model town")
    assert match.closed is True


# ---- fuzzy matching [D16] ---------------------------------------------------------------


def test_fuzzy_threshold():
    """[D16] No fuzzy below 3 characters, k=1 for 3–5 characters, k=2 from 6."""
    assert [fuzzy_limit("x" * n) for n in (1, 2, 3, 5, 6, 20)] == [0, 0, 1, 1, 2, 2]


def test_fuzzy_finds_typos():
    """ER2: a typo still finds the station, as a FUZZY match."""
    results = search(INDEX, "hauz kas")
    assert (results[0].station_id, results[0].match_type, results[0].distance) == \
        ("HZKS", "FUZZY", 1)
    assert ids("kashmiri gate")[0] == "KSHG"  # distance 2
    assert ids("rajib")[0] == "RJCK"  # typo while still typing


def test_fuzzy_respects_the_limit():
    """Three edits are never accepted, and short queries never match fuzzily."""
    assert ids("hxyz kxas") == []
    assert ids("hz") == []


def test_levenshtein_within():
    """Exact distances when within k, None when over (including the length shortcut)."""
    assert levenshtein_within("kitten", "sitting", 3) == 3
    assert levenshtein_within("kitten", "sitting", 2) is None
    assert levenshtein_within("abc", "abc", 0) == 0
    assert levenshtein_within("a", "abcd", 2) is None


# ---- T14: hostile input never raises ----------------------------------------------------


def test_t14_empty_and_whitespace_queries():
    """An empty or whitespace-only query returns []."""
    assert search(INDEX, "") == []
    assert search(INDEX, "   \t\n") == []


def test_t14_overlong_query():
    """T14/ER4: a 10 000-character string does not raise and is reported as too long."""
    hostile = ("Rajiv Chowk ‮\x00\U0001F687" * 1000)[:10_000]
    assert is_too_long(hostile)
    search(INDEX, hostile)
    assert len(normalise(hostile)) <= 100


def test_t14_random_strings_never_raise():
    """T14: 10 000 seeded random strings, including control and astral characters."""
    rng = random.Random(14)
    alphabet = "abcdefghij sec \t\n\x00́​﻿\U0001F600ÄßŞ-()'.0123456789"
    for _ in range(10_000):
        query = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
        results = search(INDEX, query)
        assert len(results) <= 8
