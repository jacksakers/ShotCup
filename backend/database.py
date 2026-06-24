import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "shotcup.db")

# Canonical 2026 FIFA World Cup team names (48 teams — actual tournament squads).
# The parser.py module imports this same list for text matching.
# Names here are the English-friendly canonical forms; see parser.py NAME_ALIASES
# for the FIFA website variants (e.g. "Korea Republic" → "South Korea").
WC_TEAMS = [
    # Group A
    "Mexico", "South Korea", "Czechia", "South Africa",
    # Group B
    "Canada", "Switzerland", "Bosnia and Herzegovina", "Qatar",
    # Group C
    "Brazil", "Morocco", "Scotland", "Haiti",
    # Group D
    "USA", "Australia", "Paraguay", "Turkey",
    # Group E
    "Germany", "Ivory Coast", "Ecuador", "Curacao",
    # Group F
    "Netherlands", "Japan", "Sweden", "Tunisia",
    # Group G
    "Egypt", "Iran", "Belgium", "New Zealand",
    # Group H
    "Spain", "Uruguay", "Cabo Verde", "Saudi Arabia",
    # Group I
    "France", "Norway", "Senegal", "Iraq",
    # Group J
    "Argentina", "Austria", "Algeria", "Jordan",
    # Group K
    "Colombia", "Portugal", "DR Congo", "Uzbekistan",
    # Group L
    "England", "Ghana", "Croatia", "Panama",
]


@contextmanager
def get_db():
    """Context manager that provides a committed SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables and seed teams on first run."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    UNIQUE NOT NULL,
                is_admin     INTEGER NOT NULL DEFAULT 0,
                total_points INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS teams (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    UNIQUE NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'Active',
                owner_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
                wins             INTEGER NOT NULL DEFAULT 0,
                draws            INTEGER NOT NULL DEFAULT 0,
                losses           INTEGER NOT NULL DEFAULT 0,
                goals_for        INTEGER NOT NULL DEFAULT 0,
                goals_against    INTEGER NOT NULL DEFAULT 0,
                clean_sheets     INTEGER NOT NULL DEFAULT 0,
                points_earned    INTEGER NOT NULL DEFAULT 0,
                reached_quarters INTEGER NOT NULL DEFAULT 0,
                reached_semis    INTEGER NOT NULL DEFAULT 0,
                reached_final    INTEGER NOT NULL DEFAULT 0,
                won_tournament   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS trades (
                id                INTEGER  PRIMARY KEY AUTOINCREMENT,
                proposer_id       INTEGER  NOT NULL REFERENCES users(id),
                receiver_id       INTEGER  NOT NULL REFERENCES users(id),
                team_offered_id   INTEGER  NOT NULL REFERENCES teams(id),
                team_requested_id INTEGER  NOT NULL REFERENCES teams(id),
                status            TEXT     NOT NULL DEFAULT 'Pending',
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Seed teams — INSERT OR IGNORE runs on every startup so that
        # teams added to WC_TEAMS are picked up without a DB reset.
        for team_name in WC_TEAMS:
            conn.execute(
                "INSERT OR IGNORE INTO teams (name) VALUES (?)",
                (team_name,),
            )

        # Initialize draft_completed setting if missing
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('draft_completed', 'false')"
        )
