"""Station search by name, alias or code (A2 Alg. 5 simplified; FR3, FR5, ER2–ER4).

A linear scan over every name with the A2 ranking rules, instead of a trie [D26]:
about 300 stations is far too few for a trie to pay for its extra code.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from metro.models import Station

MAX_QUERY_LENGTH = 100  # ER4
MAX_RESULTS = 8

# Lower rank is better (PRD §5.4).
RANK = {"CODE": 0, "NAME": 1, "PREFIX": 2, "SUBSTRING": 3, "FUZZY": 4}


@dataclass(frozen=True)
class IndexEntry:
    """One searchable text (a name, an alias or a code) for one station."""

    text: str  # already normalised
    station_id: str
    is_code: bool
    name: str  # the station's canonical name, used for sorting and display
    closed: bool


@dataclass(frozen=True)
class Match:
    """One search result. Closed stations are included so the UI can dim them."""

    station_id: str
    match_type: str  # CODE, NAME, PREFIX, SUBSTRING or FUZZY
    distance: int  # edit distance; 0 unless FUZZY
    name: str
    closed: bool


def is_too_long(text: str) -> bool:
    """True if `normalise` will cut this text, so the UI can say so (ER4)."""
    return len(text) > MAX_QUERY_LENGTH


def normalise(text: str) -> str:
    """Make text comparable: cut to 100 chars, NFKC, drop control chars, lowercase,
    collapse spaces, and expand a whole-word "sec" to "sector" (PRD §5.4)."""
    text = unicodedata.normalize("NFKC", text[:MAX_QUERY_LENGTH])
    # Tabs and newlines are control characters too, so turn whitespace into spaces first;
    # otherwise "Rajiv\tChowk" would become "rajivchowk".
    text = "".join(" " if ch.isspace() else ch for ch in text)
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("C"))
    text = " ".join(text.lower().split())
    return re.sub(r"\bsec\b", "sector", text)


def build_index(stations: Iterable[Station]) -> list[IndexEntry]:
    """One entry per name, alias and code of every station; built once at start-up."""
    index = []
    for st in stations:
        index.append(IndexEntry(normalise(st.id), st.id, True, st.name, st.closed))
        for text in (st.name, *st.aliases):
            index.append(IndexEntry(normalise(text), st.id, False, st.name, st.closed))
    return index


def fuzzy_limit(query: str) -> int:
    """Largest edit distance allowed for a FUZZY match [D16].

    0 below 3 characters (no fuzzy), 1 for 3–5 characters, 2 from 6 characters.
    """
    return min(2, len(query) // 3)


def levenshtein_within(a: str, b: str, k: int) -> int | None:
    """Edit distance between a and b if it is at most k, else None.

    The classic two-row dynamic programme, stopping early once a whole row exceeds k
    (no later row can then come back under k).
    """
    if abs(len(a) - len(b)) > k:
        return None
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            current.append(min(previous[j] + 1,                        # delete
                               current[j - 1] + 1,                     # insert
                               previous[j - 1] + (char_a != char_b)))  # substitute
        if min(current) > k:
            return None
        previous = current
    return previous[-1] if previous[-1] <= k else None


def classify(query: str, entry: IndexEntry, k: int) -> tuple[str, int] | None:
    """How `query` matches one entry, as (match_type, distance), or None for no match."""
    if entry.is_code:
        return ("CODE", 0) if query == entry.text else None
    if query == entry.text:
        return ("NAME", 0)
    if entry.text.startswith(query):
        return ("PREFIX", 0)
    if query in entry.text:
        return ("SUBSTRING", 0)
    if k == 0:
        return None
    # Compare with the whole name, and with its start, so a typo while still typing
    # (e.g. "rajib" for "Rajiv Chowk") is also found.
    distances = [d for d in (levenshtein_within(query, entry.text, k),
                             levenshtein_within(query, entry.text[:len(query)], k))
                 if d is not None]
    return ("FUZZY", min(distances)) if distances else None


def search(index: list[IndexEntry], query: str) -> list[Match]:
    """Up to 8 best matches, sorted by (rank, distance, name). Never raises (T14).

    Each station appears once, with its best-matching name, alias or code.
    """
    query = normalise(query)
    if not query:
        return []
    k = fuzzy_limit(query)
    best: dict[str, Match] = {}
    for entry in index:
        found = classify(query, entry, k)
        if found is None:
            continue
        match = Match(entry.station_id, found[0], found[1], entry.name, entry.closed)
        old = best.get(entry.station_id)
        if old is None or sort_key(match) < sort_key(old):
            best[entry.station_id] = match
    return sorted(best.values(), key=sort_key)[:MAX_RESULTS]


def sort_key(match: Match) -> tuple[int, int, str, str]:
    """Ranking order: match type, then edit distance, then name (ID breaks exact ties)."""
    return (RANK[match.match_type], match.distance, match.name, match.station_id)
