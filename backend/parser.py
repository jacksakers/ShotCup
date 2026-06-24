"""
parser.py — Pure-function FIFA standings text parser.

All public functions take plain strings / primitives and return plain dicts,
making them trivial to unit-test without any database access.
"""

import re
from database import WC_TEAMS

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

# Maps lowercased variants that may appear in FIFA copy-paste → canonical name.
NAME_ALIASES: dict[str, str] = {
    "united states": "USA",
    "usa": "USA",
    "u.s.a.": "USA",
    "korea republic": "South Korea",
    "republic of korea": "South Korea",
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "côte d ivoire": "Ivory Coast",
    "democratic republic of congo": "DR Congo",
    "congo dr": "DR Congo",
    "drc": "DR Congo",
}


def normalize_team_name(name: str) -> str:
    """Return the canonical team name for a given input string."""
    lower = name.lower().strip()
    return NAME_ALIASES.get(lower, name.strip())


# Build a combined search list: (text_to_search_for, canonical_name)
# Sorted longest-first so multi-word names match before single-word substrings.
_SEARCH_TERMS: list[tuple[str, str]] = sorted(
    [(t, t) for t in WC_TEAMS] + [(alias, canonical) for alias, canonical in NAME_ALIASES.items()],
    key=lambda x: len(x[0]),
    reverse=True,
)


# ---------------------------------------------------------------------------
# Standings parser
# ---------------------------------------------------------------------------

def parse_standings(raw_text: str) -> list[dict]:
    """Parse a raw FIFA group-stage standings block and return team statistics.

    Handles both 8-column (P W D L GF GA GD Pts) and 7-column
    (P W D L GF GA Pts) table formats.

    Args:
        raw_text: Text copied directly from the FIFA standings page.

    Returns:
        List of dicts, each with keys:
            name, wins, draws, losses, goals_for, goals_against
        Only teams that are found in the text are included.
    """
    results: list[dict] = []
    found_canonical: set[str] = set()

    for search_term, canonical in _SEARCH_TERMS:
        if canonical in found_canonical:
            continue

        escaped = re.escape(search_term)

        # --- Format A: P W D L GF GA GD Pts (GD present, signed or unsigned) ---
        pattern_a = (
            rf"\b{escaped}\b"
            r"\s+(\d+)"          # P (played)
            r"\s+(\d+)"          # W
            r"\s+(\d+)"          # D
            r"\s+(\d+)"          # L
            r"\s+(\d+)"          # GF
            r"\s+(\d+)"          # GA
            r"\s+[+\-]?\d+"      # GD  (skip — not a capture group)
            r"\s+(\d+)"          # Pts (FIFA pts — recorded but not used for scoring)
        )

        # --- Format B: P W D L GF GA Pts (no GD column) ---
        pattern_b = (
            rf"\b{escaped}\b"
            r"\s+(\d+)"          # P
            r"\s+(\d+)"          # W
            r"\s+(\d+)"          # D
            r"\s+(\d+)"          # L
            r"\s+(\d+)"          # GF
            r"\s+(\d+)"          # GA
            r"\s+(\d+)"          # Pts
        )

        match = re.search(pattern_a, raw_text, re.IGNORECASE)
        if match:
            _p, w, d, l, gf, ga, _pts = match.groups()
        else:
            match = re.search(pattern_b, raw_text, re.IGNORECASE)
            if match:
                _p, w, d, l, gf, ga, _pts = match.groups()
            else:
                continue

        results.append({
            "name": canonical,
            "wins": int(w),
            "draws": int(d),
            "losses": int(l),
            "goals_for": int(gf),
            "goals_against": int(ga),
        })
        found_canonical.add(canonical)

    return results


# ---------------------------------------------------------------------------
# Match result helper
# ---------------------------------------------------------------------------

def parse_match_result(
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
) -> dict:
    """Derive per-team stat deltas from a single match scoreline.

    Args:
        home_team:  Team name (will be normalised).
        away_team:  Team name (will be normalised).
        home_goals: Goals scored by the home side.
        away_goals: Goals scored by the away side.

    Returns:
        Dict with "home" and "away" keys, each containing:
            name, wins, draws, losses, goals_for, goals_against, clean_sheet
        These represent *incremental* values to be added to current totals.
    """
    home: dict = {
        "name": normalize_team_name(home_team),
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": home_goals,
        "goals_against": away_goals,
        "clean_sheet": 1 if away_goals == 0 else 0,
    }
    away: dict = {
        "name": normalize_team_name(away_team),
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": away_goals,
        "goals_against": home_goals,
        "clean_sheet": 1 if home_goals == 0 else 0,
    }

    if home_goals > away_goals:
        home["wins"] = 1
        away["losses"] = 1
    elif away_goals > home_goals:
        away["wins"] = 1
        home["losses"] = 1
    else:
        home["draws"] = 1
        away["draws"] = 1

    return {"home": home, "away": away}
