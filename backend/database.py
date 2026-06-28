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
    "Mexico", "South Africa",
    # Group B
    "Canada", "Switzerland", "Bosnia and Herzegovina",
    # Group C
    "Brazil", "Morocco",
    # Group D
    "USA", "Australia", "Paraguay",
    # Group E
    "Germany", "Ivory Coast", "Ecuador",
    # Group F
    "Netherlands", "Japan", "Sweden",
    # Group G
    "Egypt", "Belgium",
    # Group H
    "Spain", "Cabo Verde",
    # Group I
    "France", "Norway", "Senegal",
    # Group J
    "Argentina", "Austria", "Algeria",
    # Group K
    "Colombia", "Portugal", "DR Congo",
    # Group L
    "England", "Ghana", "Croatia",
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
        # ----------------------------------------------------------------------
        # SCHEMA MIGRATION CHECK FOR TRADES TABLE
        # ----------------------------------------------------------------------
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        if cursor.fetchone():
            cursor_cols = conn.execute("PRAGMA table_info(trades)")
            columns = [row["name"] for row in cursor_cols.fetchall()]
            if "offered_team_ids" not in columns:
                # Need migration from old trades table schema to new schema!
                conn.execute("ALTER TABLE trades RENAME TO trades_old")
                
                # Create new trades table
                conn.execute("""
                    CREATE TABLE trades (
                        id                INTEGER  PRIMARY KEY AUTOINCREMENT,
                        proposer_id       INTEGER  NOT NULL REFERENCES users(id),
                        receiver_id       INTEGER  REFERENCES users(id),
                        offered_team_ids  TEXT     NOT NULL,
                        requested_team_ids TEXT    NOT NULL,
                        accepted_team_id  INTEGER  REFERENCES teams(id),
                        status            TEXT     NOT NULL DEFAULT 'Pending',
                        created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                
                # Migrate records
                old_rows = conn.execute("SELECT * FROM trades_old").fetchall()
                for row in old_rows:
                    row_dict = dict(row)
                    prop_id = row_dict["proposer_id"]
                    recv_id = row_dict["receiver_id"]
                    t_offered = row_dict.get("team_offered_id")
                    t_requested = row_dict.get("team_requested_id")
                    st = row_dict["status"]
                    created = row_dict["created_at"]
                    
                    offered_str = str(t_offered) if t_offered is not None else ""
                    requested_str = str(t_requested) if t_requested is not None else ""
                    acc_id = t_requested if st == 'Accepted' else None
                    
                    conn.execute("""
                        INSERT INTO trades (
                            proposer_id, receiver_id, offered_team_ids, requested_team_ids,
                            accepted_team_id, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (prop_id, recv_id, offered_str, requested_str, acc_id, st, created))
                
                conn.execute("DROP TABLE trades_old")

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
                receiver_id       INTEGER  REFERENCES users(id),
                offered_team_ids  TEXT     NOT NULL,
                requested_team_ids TEXT    NOT NULL,
                accepted_team_id  INTEGER  REFERENCES teams(id),
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
