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

# Maps lowercased FIFA-website variants → canonical name used in WC_TEAMS.
NAME_ALIASES: dict[str, str] = {
    # USA
    "united states": "USA",
    "usa": "USA",
    "u.s.a.": "USA",
    "united states of america": "USA",
    # Korea
    "korea republic": "South Korea",
    "republic of korea": "South Korea",
    # Iran
    "ir iran": "Iran",
    "islamic republic of iran": "Iran",
    # Ivory Coast
    "côte d'ivoire": "Ivory Coast",
    "cote d'ivoire": "Ivory Coast",
    "côte d ivoire": "Ivory Coast",
    "cote d ivoire": "Ivory Coast",
    # DR Congo
    "democratic republic of congo": "DR Congo",
    "congo dr": "DR Congo",
    "drc": "DR Congo",
    "dr. congo": "DR Congo",
    # Turkey
    "türkiye": "Turkey",
    "turkiye": "Turkey",
    "turkey": "Turkey",
    # Curacao
    "curaçao": "Curacao",
    # Bosnia
    "bosnia": "Bosnia and Herzegovina",
    "bih": "Bosnia and Herzegovina",
    # Cape Verde
    "cape verde": "Cabo Verde",
    # Czech Republic
    "czech republic": "Czechia",
    # Czechia alternate
    "czechia": "Czechia",
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

# Fast exact-match lookup used by the multiline parser: lowercase → canonical
_NAME_LOOKUP: dict[str, str] = {term.lower(): canonical for term, canonical in _SEARCH_TERMS}


# ---------------------------------------------------------------------------
# Standings parser
# ---------------------------------------------------------------------------

def _parse_stats_line(stats_line: str) -> list[int] | None:
    """Parse a tab/space-separated stats line into a list of integers.

    Handles both unsigned and signed values (+3, -6, etc.).
    Returns None if fewer than 6 integers can be extracted.
    """
    nums: list[int] = []
    for tok in re.split(r"[\t ]+", stats_line.strip()):
        tok = tok.strip()
        if not tok:
            continue
        try:
            nums.append(int(tok))
        except ValueError:
            # Skip non-numeric tokens (e.g. "Form", stray letters)
            pass
    return nums if len(nums) >= 6 else None


def parse_standings(raw_text: str) -> list[dict]:
    """Parse a raw FIFA group-stage standings block and return team statistics.

    Supports two formats automatically:

    **Inline** (name + stats on one line — common in simple tables):
        ``Argentina  3  3  0  0  9  0  +9  9``

    **Multiline** (FIFA website copy-paste — name on its own line, stats below):
        ::
            Argentina
            2  2  0  0  5  0  +5  -2  6

    Both 8-column (P W D L GF GA GD Pts) and 9-column
    (P W D L GF GA GD TCS Pts) formats are handled.
    Negative goal-difference and TCS values are handled correctly.

    Args:
        raw_text: Text copied directly from the FIFA standings page.

    Returns:
        List of dicts, each with keys:
            name, wins, draws, losses, goals_for, goals_against
        Only teams found in the text are included.
    """
    results: list[dict] = []
    found_canonical: set[str] = set()

    # -----------------------------------------------------------------------
    # Strategy 1 — multiline format
    # Team name appears on its own line; stats are on the next non-empty line
    # that starts with a digit.
    # -----------------------------------------------------------------------
    lines = [ln.strip() for ln in raw_text.splitlines()]

    for i, line in enumerate(lines):
        if not line:
            continue

        canonical = _NAME_LOOKUP.get(line.lower())
        if not canonical or canonical in found_canonical:
            continue

        # Look ahead up to 6 lines for a stats row
        for j in range(i + 1, min(i + 7, len(lines))):
            stats_line = lines[j]
            if not stats_line:
                continue
            # Stats line must start with a digit (the P column)
            if not stats_line[0].isdigit():
                break  # Hit another text line — stop looking

            nums = _parse_stats_line(stats_line)
            if nums and len(nums) >= 6:
                # Columns: [P, W, D, L, GF, GA, (GD), (TCS), (Pts)]
                results.append({
                    "name": canonical,
                    "wins": nums[1],
                    "draws": nums[2],
                    "losses": nums[3],
                    "goals_for": nums[4],
                    "goals_against": nums[5],
                })
                found_canonical.add(canonical)
            break  # Whether we got stats or not, move on

    # -----------------------------------------------------------------------
    # Strategy 2 — inline format (fallback for simple tables)
    # Handles signed GD/TCS by using [+\-]?\d+ for skipped columns.
    # -----------------------------------------------------------------------
    for search_term, canonical in _SEARCH_TERMS:
        if canonical in found_canonical:
            continue

        escaped = re.escape(search_term)

        # 9-col: P W D L GF GA GD TCS Pts  (skip both GD and TCS)
        pattern_9 = (
            rf"\b{escaped}\b"
            r"\s+(\d+)"           # P
            r"\s+(\d+)"           # W
            r"\s+(\d+)"           # D
            r"\s+(\d+)"           # L
            r"\s+(\d+)"           # GF
            r"\s+(\d+)"           # GA
            r"\s+[+\-]?\d+"       # GD  (skip)
            r"\s+[+\-]?\d+"       # TCS (skip)
            r"\s+(\d+)"           # Pts
        )
        # 8-col: P W D L GF GA GD Pts  (skip GD)
        pattern_8 = (
            rf"\b{escaped}\b"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+[+\-]?\d+"       # GD (skip)
            r"\s+(\d+)"           # Pts
        )
        # 7-col: P W D L GF GA Pts  (no GD)
        pattern_7 = (
            rf"\b{escaped}\b"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
            r"\s+(\d+)"
        )

        match = None
        for pat in (pattern_9, pattern_8, pattern_7):
            match = re.search(pat, raw_text, re.IGNORECASE)
            if match:
                break

        if not match:
            continue

        groups = match.groups()
        # groups: (P, W, D, L, GF, GA, [Pts])  — P and Pts are unused
        results.append({
            "name": canonical,
            "wins": int(groups[1]),
            "draws": int(groups[2]),
            "losses": int(groups[3]),
            "goals_for": int(groups[4]),
            "goals_against": int(groups[5]),
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
