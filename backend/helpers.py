import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
import bcrypt as _bcrypt

from database import get_db

SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE-THIS-IN-PRODUCTION")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7  # tokens valid for 1 week
TEAM_STATUS_ACTIVE = "Active"  # teams.status values in DB should use this exact casing

bearer_scheme = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


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


def _calculate_team_points(team: dict, champion_team_id: Optional[int] = None) -> int:
    """Return total fantasy points for a team based on its current stats."""
    pts = 0
    pts += team["wins"] * 3
    pts += team["draws"] * 1
    pts += team["goals_for"] * 1
    pts += team["clean_sheets"] * 2
    if team["reached_quarters"]:
        pts += 3
    if team["reached_semis"]:
        pts += 4
    if team["reached_final"]:
        pts += 5
    if team["won_tournament"]:
        pts += 8
    if champion_team_id is not None and team["id"] == champion_team_id:
        pts += 12
    return pts


def _recalculate_all_scores(conn) -> None:
    """Recompute points_earned for every team, then total_points for every user."""
    active_winners = conn.execute(
        "SELECT id FROM teams WHERE won_tournament = 1 AND status = ?",
        (TEAM_STATUS_ACTIVE,),
    ).fetchall()
    # In the current progression state, semifinal winners are marked as won_tournament
    # while both finalists remain Active before the final. Apply the champion bonus
    # only once there is exactly one Active won_tournament team left.
    # If there are zero (pre-finals) or multiple active winners, no champion bonus is applied.
    champion_team_id = active_winners[0]["id"] if len(active_winners) == 1 else None

    teams = conn.execute("SELECT * FROM teams").fetchall()
    for team in teams:
        team_dict = dict(team)
        pts = _calculate_team_points(team_dict, champion_team_id=champion_team_id)
        conn.execute("UPDATE teams SET points_earned = ? WHERE id = ?", (pts, team_dict["id"]))

    users = conn.execute("SELECT id FROM users").fetchall()
    for user in users:
        total = conn.execute(
            "SELECT COALESCE(SUM(points_earned), 0) FROM teams WHERE owner_id = ?",
            (user["id"],),
        ).fetchone()[0]
        conn.execute("UPDATE users SET total_points = ? WHERE id = ?", (total, user["id"]))


def _row_to_team(row) -> dict:
    d = dict(row)
    for key in ("reached_quarters", "reached_semis", "reached_final", "won_tournament", "is_admin"):
        if key in d:
            d[key] = bool(d[key])
    return d


def _row_to_trade_response(conn, row) -> dict:
    trade = dict(row)
    
    # Parse offered team IDs
    offered_ids = [int(x) for x in trade["offered_team_ids"].split(",") if x.strip()]
    offered_names = []
    if offered_ids:
        placeholders = ",".join("?" for _ in offered_ids)
        teams = conn.execute(
            f"SELECT name FROM teams WHERE id IN ({placeholders})", offered_ids
        ).fetchall()
        offered_names = [r["name"] for r in teams]
        
    # Parse requested team IDs
    requested_ids = [int(x) for x in trade["requested_team_ids"].split(",") if x.strip()]
    requested_names = []
    if requested_ids:
        placeholders = ",".join("?" for _ in requested_ids)
        teams = conn.execute(
            f"SELECT name FROM teams WHERE id IN ({placeholders})", requested_ids
        ).fetchall()
        requested_names = [r["name"] for r in teams]
        
    # Get accepted team name
    accepted_name = None
    if trade["accepted_team_id"]:
        t_row = conn.execute(
            "SELECT name FROM teams WHERE id = ?", (trade["accepted_team_id"],)
        ).fetchone()
        if t_row:
            accepted_name = t_row["name"]
            
    # Proposer username
    p_row = conn.execute(
        "SELECT username FROM users WHERE id = ?", (trade["proposer_id"],)
    ).fetchone()
    proposer_username = p_row["username"] if p_row else "Unknown"
    
    # Receiver username
    receiver_username = None
    if trade["receiver_id"]:
        r_row = conn.execute(
            "SELECT username FROM users WHERE id = ?", (trade["receiver_id"],)
        ).fetchone()
        if r_row:
            receiver_username = r_row["username"]

    return {
        "id": trade["id"],
        "proposer_id": trade["proposer_id"],
        "proposer_username": proposer_username,
        "receiver_id": trade["receiver_id"],
        "receiver_username": receiver_username,
        "offered_team_ids": offered_ids,
        "offered_team_names": offered_names,
        "requested_team_ids": requested_ids,
        "requested_team_names": requested_names,
        "accepted_team_id": trade["accepted_team_id"],
        "accepted_team_name": accepted_name,
        "status": trade["status"],
        "created_at": str(trade["created_at"]),
    }
