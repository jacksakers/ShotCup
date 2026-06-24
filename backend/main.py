"""
main.py — FastAPI application: all routes, auth, and scoring logic.
"""

import os
import random
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import bcrypt as _bcrypt
from dotenv import load_dotenv

from database import get_db, init_db
from models import (
    AdminAuthRequest,
    LeaderboardEntry,
    MatchResultRequest,
    ParseStandingsRequest,
    SettingUpdate,
    SiteAuthRequest,
    TeamOverrideRequest,
    TeamResponse,
    TokenResponse,
    TradeCreate,
    TradeRespond,
    TradeResponse,
    UserCreate,
    UserPointsOverrideRequest,
    UserResponse,
)
from parser import normalize_team_name, parse_match_result, parse_standings

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE-THIS-IN-PRODUCTION")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # tokens valid for 1 week

bearer_scheme = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Startup / lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _sync_passwords_from_env()
    yield


def _sync_passwords_from_env() -> None:
    """Hash passwords from .env and upsert them into the settings table.

    Called on every startup so that changing .env + restarting updates the passwords.
    """
    site_pw = os.getenv("SITE_PASSWORD")
    admin_pw = os.getenv("ADMIN_PASSWORD")

    with get_db() as conn:
        if site_pw:
            hashed = _hash_password(site_pw)
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('site_password_hash', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (hashed,),
            )
        if admin_pw:
            hashed = _hash_password(admin_pw)
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('admin_password_hash', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (hashed,),
            )


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ShotCup",
    description="World Cup Fantasy League — family edition",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _create_token(token_type: str) -> str:
    payload = {
        "type": token_type,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str, required_type: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    if payload.get("type") != required_type:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return payload


async def require_site_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _decode_token(credentials.credentials, "site")


async def require_admin_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _decode_token(credentials.credentials, "admin")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _calculate_team_points(team: dict) -> int:
    """Return total fantasy points for a team based on its current stats."""
    pts = 0
    pts += team["wins"] * 3
    pts += team["draws"] * 1
    pts += team["goals_for"] * 1
    pts += team["clean_sheets"] * 2
    if team["reached_quarters"]:
        pts += 3
    if team["reached_semis"]:
        pts += 5
    if team["reached_final"]:
        pts += 7
    if team["won_tournament"]:
        pts += 10
    return pts


def _recalculate_all_scores(conn) -> None:
    """Recompute points_earned for every team, then total_points for every user."""
    teams = conn.execute("SELECT * FROM teams").fetchall()
    for team in teams:
        team_dict = dict(team)
        pts = _calculate_team_points(team_dict)
        conn.execute("UPDATE teams SET points_earned = ? WHERE id = ?", (pts, team_dict["id"]))

    users = conn.execute("SELECT id FROM users").fetchall()
    for user in users:
        total = conn.execute(
            "SELECT COALESCE(SUM(points_earned), 0) FROM teams WHERE owner_id = ?",
            (user["id"],),
        ).fetchone()[0]
        conn.execute("UPDATE users SET total_points = ? WHERE id = ?", (total, user["id"]))


# ---------------------------------------------------------------------------
# DB row → response model helpers
# ---------------------------------------------------------------------------

def _row_to_team(row) -> dict:
    d = dict(row)
    for key in ("reached_quarters", "reached_semis", "reached_final", "won_tournament", "is_admin"):
        if key in d:
            d[key] = bool(d[key])
    return d


def _get_trade_full(conn, trade_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT
            tr.*,
            p.username  AS proposer_username,
            r.username  AS receiver_username,
            t1.name     AS team_offered_name,
            t2.name     AS team_requested_name
        FROM trades tr
        JOIN users  p  ON tr.proposer_id       = p.id
        JOIN users  r  ON tr.receiver_id        = r.id
        JOIN teams  t1 ON tr.team_offered_id    = t1.id
        JOIN teams  t2 ON tr.team_requested_id  = t2.id
        WHERE tr.id = ?
        """,
        (trade_id,),
    ).fetchone()
    return dict(row) if row else None


# ===========================================================================
# ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/auth/site", response_model=TokenResponse, tags=["Auth"])
def site_login(req: SiteAuthRequest):
    """Exchange the family site password for a bearer token."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'site_password_hash'"
        ).fetchone()
        if not row or not _verify_password(req.password, row["value"]):
            raise HTTPException(status_code=401, detail="Incorrect password")
    return TokenResponse(access_token=_create_token("site"))


@app.post("/api/auth/admin", response_model=TokenResponse, tags=["Auth"])
def admin_login(req: AdminAuthRequest):
    """Exchange the admin password for a bearer token with elevated privileges."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'admin_password_hash'"
        ).fetchone()
        if not row or not _verify_password(req.password, row["value"]):
            raise HTTPException(status_code=401, detail="Incorrect password")
    return TokenResponse(access_token=_create_token("admin"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/users", response_model=list[UserResponse], tags=["Users"])
def list_users(_auth=Depends(require_site_auth)):
    """List all registered players."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin, total_points FROM users ORDER BY username"
        ).fetchall()
    return [_row_to_team(r) for r in rows]


@app.post("/api/users", response_model=UserResponse, status_code=201, tags=["Users"])
def create_user(req: UserCreate, _auth=Depends(require_site_auth)):
    """Register a new player. Only allowed before the draft is run."""
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    with get_db() as conn:
        draft_row = conn.execute(
            "SELECT value FROM settings WHERE key = 'draft_completed'"
        ).fetchone()
        if draft_row and draft_row["value"] == "true":
            raise HTTPException(status_code=400, detail="Cannot add players after the draft")

        try:
            cursor = conn.execute(
                "INSERT INTO users (username) VALUES (?)", (username,)
            )
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")

        row = conn.execute(
            "SELECT id, username, is_admin, total_points FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return _row_to_team(row)


@app.get("/api/users/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: int, _auth=Depends(require_site_auth)):
    """Get a single player's details."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, total_points FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_team(row)


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@app.get("/api/teams", response_model=list[TeamResponse], tags=["Teams"])
def list_teams(_auth=Depends(require_site_auth)):
    """List all 48 World Cup teams with owner and fantasy score information."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT t.*, u.username AS owner_username
            FROM   teams t
            LEFT JOIN users u ON t.owner_id = u.id
            ORDER BY t.name
            """
        ).fetchall()
    return [_row_to_team(r) for r in rows]


@app.get("/api/teams/{team_id}", response_model=TeamResponse, tags=["Teams"])
def get_team(team_id: int, _auth=Depends(require_site_auth)):
    """Get a single team."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT t.*, u.username AS owner_username
            FROM   teams t
            LEFT JOIN users u ON t.owner_id = u.id
            WHERE  t.id = ?
            """,
            (team_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Team not found")
    return _row_to_team(row)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@app.get("/api/leaderboard", response_model=list[LeaderboardEntry], tags=["Leaderboard"])
def get_leaderboard(_auth=Depends(require_site_auth)):
    """Return all players ranked by total fantasy points (descending)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id           AS user_id,
                u.username,
                u.total_points,
                COUNT(t.id)    AS team_count
            FROM  users u
            LEFT JOIN teams t ON t.owner_id = u.id
            GROUP BY u.id
            ORDER BY u.total_points DESC, u.username ASC
            """
        ).fetchall()

    return [
        LeaderboardEntry(rank=rank, **dict(row))
        for rank, row in enumerate(rows, start=1)
    ]


# ---------------------------------------------------------------------------
# Draft
# ---------------------------------------------------------------------------

@app.post("/api/admin/draft", tags=["Admin"])
def run_draft(_auth=Depends(require_admin_auth)):
    """Randomly distribute all Active teams among registered players (round-robin).

    Teams beyond an even division are assigned to the first players in the
    shuffled order (no 'House' bucket — every team gets an owner).
    """
    with get_db() as conn:
        draft_row = conn.execute(
            "SELECT value FROM settings WHERE key = 'draft_completed'"
        ).fetchone()
        if draft_row and draft_row["value"] == "true":
            raise HTTPException(status_code=400, detail="Draft has already been completed")

        users = conn.execute("SELECT id FROM users").fetchall()
        if not users:
            raise HTTPException(status_code=400, detail="No players registered yet")

        teams = conn.execute("SELECT id FROM teams WHERE status = 'Active'").fetchall()
        team_ids = [t["id"] for t in teams]
        user_ids = [u["id"] for u in users]

        random.shuffle(team_ids)

        for i, team_id in enumerate(team_ids):
            conn.execute(
                "UPDATE teams SET owner_id = ? WHERE id = ?",
                (user_ids[i % len(user_ids)], team_id),
            )

        conn.execute(
            "UPDATE settings SET value = 'true' WHERE key = 'draft_completed'"
        )

    return {
        "message": "Draft completed successfully",
        "teams_distributed": len(team_ids),
        "players": len(user_ids),
        "teams_per_player": len(team_ids) // len(user_ids),
        "extra_teams": len(team_ids) % len(user_ids),
    }


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

@app.get("/api/trades", response_model=list[TradeResponse], tags=["Trades"])
def list_trades(
    user_id: Optional[int] = Query(None, description="Filter trades involving this user"),
    trade_status: Optional[str] = Query(None, alias="status", description="Filter by status (Pending/Accepted/Rejected/Vetoed)"),
    _auth=Depends(require_site_auth),
):
    """List trades, optionally filtered by user or status."""
    query = """
        SELECT
            tr.*,
            p.username  AS proposer_username,
            r.username  AS receiver_username,
            t1.name     AS team_offered_name,
            t2.name     AS team_requested_name
        FROM trades tr
        JOIN users  p  ON tr.proposer_id       = p.id
        JOIN users  r  ON tr.receiver_id        = r.id
        JOIN teams  t1 ON tr.team_offered_id    = t1.id
        JOIN teams  t2 ON tr.team_requested_id  = t2.id
        WHERE 1=1
    """
    params: list = []
    if user_id is not None:
        query += " AND (tr.proposer_id = ? OR tr.receiver_id = ?)"
        params += [user_id, user_id]
    if trade_status is not None:
        query += " AND tr.status = ?"
        params.append(trade_status)
    query += " ORDER BY tr.created_at DESC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/trades", response_model=TradeResponse, status_code=201, tags=["Trades"])
def propose_trade(req: TradeCreate, _auth=Depends(require_site_auth)):
    """Propose a trade: offer one of your teams in exchange for another player's team."""
    with get_db() as conn:
        # Validate proposer owns the offered team
        offered_row = conn.execute(
            "SELECT owner_id FROM teams WHERE id = ?", (req.team_offered_id,)
        ).fetchone()
        if not offered_row or offered_row["owner_id"] != req.proposer_id:
            raise HTTPException(status_code=400, detail="You don't own the offered team")

        # Validate the requested team has an owner
        requested_row = conn.execute(
            "SELECT owner_id FROM teams WHERE id = ?", (req.team_requested_id,)
        ).fetchone()
        if not requested_row or not requested_row["owner_id"]:
            raise HTTPException(status_code=400, detail="Requested team has no owner")

        receiver_id = requested_row["owner_id"]
        if receiver_id == req.proposer_id:
            raise HTTPException(status_code=400, detail="Cannot trade with yourself")

        # Prevent duplicate pending trades
        duplicate = conn.execute(
            """
            SELECT id FROM trades
            WHERE proposer_id = ? AND team_offered_id = ? AND team_requested_id = ?
              AND status = 'Pending'
            """,
            (req.proposer_id, req.team_offered_id, req.team_requested_id),
        ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="Identical trade already pending")

        cursor = conn.execute(
            """
            INSERT INTO trades (proposer_id, receiver_id, team_offered_id, team_requested_id)
            VALUES (?, ?, ?, ?)
            """,
            (req.proposer_id, receiver_id, req.team_offered_id, req.team_requested_id),
        )
        trade_id = cursor.lastrowid
        trade = _get_trade_full(conn, trade_id)

    return trade


@app.put("/api/trades/{trade_id}/respond", response_model=TradeResponse, tags=["Trades"])
def respond_to_trade(trade_id: int, req: TradeRespond, _auth=Depends(require_site_auth)):
    """Accept or reject a pending trade.  ``user_id`` in the body must match the receiver."""
    with get_db() as conn:
        trade_row = conn.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        if not trade_row:
            raise HTTPException(status_code=404, detail="Trade not found")

        trade = dict(trade_row)
        if trade["status"] != "Pending":
            raise HTTPException(status_code=400, detail="Trade is no longer pending")
        if trade["receiver_id"] != req.user_id:
            raise HTTPException(status_code=403, detail="Only the trade receiver can respond")

        if req.action == "accept":
            # Swap ownership
            conn.execute(
                "UPDATE teams SET owner_id = ? WHERE id = ?",
                (trade["receiver_id"], trade["team_offered_id"]),
            )
            conn.execute(
                "UPDATE teams SET owner_id = ? WHERE id = ?",
                (trade["proposer_id"], trade["team_requested_id"]),
            )
            conn.execute("UPDATE trades SET status = 'Accepted' WHERE id = ?", (trade_id,))

            # Cancel other pending trades that involve either of these two teams
            conn.execute(
                """
                UPDATE trades SET status = 'Rejected'
                WHERE  id != ? AND status = 'Pending'
                  AND (   team_offered_id   IN (?, ?)
                       OR team_requested_id IN (?, ?))
                """,
                (
                    trade_id,
                    trade["team_offered_id"], trade["team_requested_id"],
                    trade["team_offered_id"], trade["team_requested_id"],
                ),
            )

            # Recalculate scores so the leaderboard stays consistent
            _recalculate_all_scores(conn)
        else:
            conn.execute("UPDATE trades SET status = 'Rejected' WHERE id = ?", (trade_id,))

        return _get_trade_full(conn, trade_id)


# ---------------------------------------------------------------------------
# Admin — standings parser
# ---------------------------------------------------------------------------

@app.post("/api/admin/parse-standings", tags=["Admin"])
def parse_standings_endpoint(
    req: ParseStandingsRequest,
    _auth=Depends(require_admin_auth),
):
    """Paste raw FIFA group-stage standings text to bulk-update team stats.

    The parser searches for known team names and extracts W/D/L/GF/GA.
    After updating the database, all fantasy scores are recalculated automatically.
    """
    results = parse_standings(req.raw_text)
    if not results:
        raise HTTPException(
            status_code=400,
            detail="No recognisable team data found. Check that the pasted text includes team names and match stats.",
        )

    updated: list[str] = []
    skipped: list[str] = []

    with get_db() as conn:
        for team_data in results:
            row = conn.execute(
                "SELECT id FROM teams WHERE LOWER(name) = LOWER(?)", (team_data["name"],)
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE teams
                    SET wins = ?, draws = ?, losses = ?, goals_for = ?, goals_against = ?
                    WHERE id = ?
                    """,
                    (
                        team_data["wins"],
                        team_data["draws"],
                        team_data["losses"],
                        team_data["goals_for"],
                        team_data["goals_against"],
                        row["id"],
                    ),
                )
                updated.append(team_data["name"])
            else:
                skipped.append(team_data["name"])

        _recalculate_all_scores(conn)

    return {"updated_teams": updated, "skipped_teams": skipped, "count": len(updated)}


# ---------------------------------------------------------------------------
# Admin — match result (knockouts + clean sheets)
# ---------------------------------------------------------------------------

@app.post("/api/admin/match-result", tags=["Admin"])
def submit_match_result(
    req: MatchResultRequest,
    _auth=Depends(require_admin_auth),
):
    """Record a single match result.

    - Increments W/D/L, GF, GA, and clean sheets for both teams.
    - If ``is_knockout=true``, the winner advances to the next round
      and the loser is marked Eliminated.
    - For penalty shootouts, pass equal goals and set ``winner_team`` explicitly.
    """
    result = parse_match_result(req.home_team, req.away_team, req.home_goals, req.away_goals)

    with get_db() as conn:
        for side in ("home", "away"):
            td = result[side]
            row = conn.execute(
                "SELECT id FROM teams WHERE LOWER(name) = LOWER(?)", (td["name"],)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Team not found: '{td['name']}'")

            conn.execute(
                """
                UPDATE teams
                SET wins          = wins          + ?,
                    draws         = draws         + ?,
                    losses        = losses        + ?,
                    goals_for     = goals_for     + ?,
                    goals_against = goals_against + ?,
                    clean_sheets  = clean_sheets  + ?
                WHERE id = ?
                """,
                (
                    td["wins"], td["draws"], td["losses"],
                    td["goals_for"], td["goals_against"], td["clean_sheet"],
                    row["id"],
                ),
            )

        if req.is_knockout:
            # Determine winner
            if req.winner_team:
                winner_name = normalize_team_name(req.winner_team)
                loser_name = (
                    result["away"]["name"]
                    if winner_name.lower() == result["home"]["name"].lower()
                    else result["home"]["name"]
                )
            elif req.home_goals > req.away_goals:
                winner_name, loser_name = result["home"]["name"], result["away"]["name"]
            elif req.away_goals > req.home_goals:
                winner_name, loser_name = result["away"]["name"], result["home"]["name"]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Scores are equal. For a penalty shootout, supply 'winner_team'.",
                )

            winner_row = conn.execute(
                """
                SELECT id, reached_quarters, reached_semis, reached_final, won_tournament
                FROM   teams WHERE LOWER(name) = LOWER(?)
                """,
                (winner_name,),
            ).fetchone()
            if winner_row:
                w = dict(winner_row)
                # Advance to the next round not yet reached
                if not w["reached_quarters"]:
                    conn.execute("UPDATE teams SET reached_quarters = 1 WHERE id = ?", (w["id"],))
                elif not w["reached_semis"]:
                    conn.execute("UPDATE teams SET reached_semis = 1 WHERE id = ?", (w["id"],))
                elif not w["reached_final"]:
                    conn.execute("UPDATE teams SET reached_final = 1 WHERE id = ?", (w["id"],))
                else:
                    conn.execute("UPDATE teams SET won_tournament = 1 WHERE id = ?", (w["id"],))

            conn.execute(
                "UPDATE teams SET status = 'Eliminated' WHERE LOWER(name) = LOWER(?)",
                (loser_name,),
            )

        _recalculate_all_scores(conn)

    return {
        "message": "Match result recorded",
        "home": result["home"],
        "away": result["away"],
    }


# ---------------------------------------------------------------------------
# Admin — manual overrides
# ---------------------------------------------------------------------------

@app.put("/api/admin/teams/{team_id}", tags=["Admin"])
def override_team(
    team_id: int,
    req: TeamOverrideRequest,
    _auth=Depends(require_admin_auth),
):
    """Manually update any combination of a team's stats or status."""
    updates: dict = {}
    bool_fields = {"reached_quarters", "reached_semis", "reached_final", "won_tournament"}
    for field in (
        "wins", "draws", "losses", "goals_for", "goals_against",
        "clean_sheets", "reached_quarters", "reached_semis",
        "reached_final", "won_tournament", "status",
    ):
        val = getattr(req, field)
        if val is not None:
            updates[field] = int(val) if field in bool_fields else val

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [team_id]

    with get_db() as conn:
        result = conn.execute(f"UPDATE teams SET {set_clause} WHERE id = ?", values)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Team not found")
        _recalculate_all_scores(conn)

    return {"message": "Team updated"}


@app.put("/api/admin/users/{user_id}/points", tags=["Admin"])
def override_user_points(
    user_id: int,
    req: UserPointsOverrideRequest,
    _auth=Depends(require_admin_auth),
):
    """Manually set a player's total points (emergency override)."""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE users SET total_points = ? WHERE id = ?", (req.total_points, user_id)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User points updated"}


@app.delete("/api/admin/trades/{trade_id}", tags=["Admin"])
def veto_trade(trade_id: int, _auth=Depends(require_admin_auth)):
    """Cancel or reverse a trade.

    - If the trade is Pending, it is Rejected.
    - If the trade was Accepted, ownership is reversed and the trade is marked Vetoed.
    """
    with get_db() as conn:
        trade_row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not trade_row:
            raise HTTPException(status_code=404, detail="Trade not found")

        trade = dict(trade_row)

        if trade["status"] == "Accepted":
            # Reverse the ownership swap
            conn.execute(
                "UPDATE teams SET owner_id = ? WHERE id = ?",
                (trade["proposer_id"], trade["team_offered_id"]),
            )
            conn.execute(
                "UPDATE teams SET owner_id = ? WHERE id = ?",
                (trade["receiver_id"], trade["team_requested_id"]),
            )
            conn.execute("UPDATE trades SET status = 'Vetoed' WHERE id = ?", (trade_id,))
            _recalculate_all_scores(conn)
        elif trade["status"] == "Pending":
            conn.execute("UPDATE trades SET status = 'Rejected' WHERE id = ?", (trade_id,))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot veto a trade with status '{trade['status']}'",
            )

    return {"message": "Trade vetoed"}


# ---------------------------------------------------------------------------
# Admin — settings
# ---------------------------------------------------------------------------

@app.get("/api/settings", tags=["Admin"])
def get_settings(_auth=Depends(require_admin_auth)):
    """Return all settings (passwords are excluded)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key NOT LIKE '%password%'"
        ).fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.put("/api/settings/{key}", tags=["Admin"])
def update_setting(key: str, req: SettingUpdate, _auth=Depends(require_admin_auth)):
    """Update a non-password setting."""
    if "password" in key.lower():
        raise HTTPException(status_code=400, detail="Use /api/auth endpoints to manage passwords")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, req.value),
        )
    return {"message": "Setting updated"}
