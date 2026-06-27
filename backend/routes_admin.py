import random
from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from models import (
    ParseStandingsRequest,
    MatchResultRequest,
    TeamOverrideRequest,
    UserPointsOverrideRequest,
    SettingUpdate
)
from parser import normalize_team_name, parse_match_result, parse_standings
from helpers import require_admin_auth, _recalculate_all_scores

admin_router = APIRouter()


@admin_router.post("/api/admin/draft", tags=["Admin"])
def run_draft(_auth=Depends(require_admin_auth)):
    """Randomly distribute all Active teams among registered players (round-robin)."""
    with get_db() as conn:
        draft_row = conn.execute("SELECT value FROM settings WHERE key = 'draft_completed'").fetchone()
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
            conn.execute("UPDATE teams SET owner_id = ? WHERE id = ?", (user_ids[i % len(user_ids)], team_id))

        conn.execute("UPDATE settings SET value = 'true' WHERE key = 'draft_completed'")

    return {
        "message": "Draft completed successfully",
        "teams_distributed": len(team_ids),
        "players": len(user_ids),
        "teams_per_player": len(team_ids) // len(user_ids),
        "extra_teams": len(team_ids) % len(user_ids),
    }


@admin_router.post("/api/admin/parse-standings", tags=["Admin"])
def parse_standings_endpoint(req: ParseStandingsRequest, _auth=Depends(require_admin_auth)):
    """Paste raw FIFA group-stage standings text to bulk-update team stats."""
    results = parse_standings(req.raw_text)
    if not results:
        raise HTTPException(status_code=400, detail="No recognisable team data found.")

    updated, skipped = [], []
    with get_db() as conn:
        for team_data in results:
            row = conn.execute("SELECT id FROM teams WHERE LOWER(name) = LOWER(?)", (team_data["name"],)).fetchone()
            if row:
                conn.execute(
                    "UPDATE teams SET wins = ?, draws = ?, losses = ?, goals_for = ?, goals_against = ? WHERE id = ?",
                    (team_data["wins"], team_data["draws"], team_data["losses"], team_data["goals_for"], team_data["goals_against"], row["id"]),
                )
                updated.append(team_data["name"])
            else:
                skipped.append(team_data["name"])
        _recalculate_all_scores(conn)

    return {"updated_teams": updated, "skipped_teams": skipped, "count": len(updated)}


@admin_router.post("/api/admin/match-result", tags=["Admin"])
def submit_match_result(req: MatchResultRequest, _auth=Depends(require_admin_auth)):
    """Record a single match result."""
    result = parse_match_result(req.home_team, req.away_team, req.home_goals, req.away_goals)

    with get_db() as conn:
        for side in ("home", "away"):
            td = result[side]
            row = conn.execute("SELECT id FROM teams WHERE LOWER(name) = LOWER(?)", (td["name"],)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Team not found: '{td['name']}'")

            conn.execute(
                """
                UPDATE teams
                SET wins = wins + ?, draws = draws + ?, losses = losses + ?,
                    goals_for = goals_for + ?, goals_against = goals_against + ?, clean_sheets = clean_sheets + ?
                WHERE id = ?
                """,
                (td["wins"], td["draws"], td["losses"], td["goals_for"], td["goals_against"], td["clean_sheet"], row["id"]),
            )

        if req.is_knockout:
            if req.winner_team:
                winner_name = normalize_team_name(req.winner_team)
                loser_name = result["away"]["name"] if winner_name.lower() == result["home"]["name"].lower() else result["home"]["name"]
            elif req.home_goals > req.away_goals:
                winner_name, loser_name = result["home"]["name"], result["away"]["name"]
            elif req.away_goals > req.home_goals:
                winner_name, loser_name = result["away"]["name"], result["home"]["name"]
            else:
                raise HTTPException(status_code=400, detail="Scores are equal. Supply 'winner_team'.")

            winner_row = conn.execute("SELECT id, reached_quarters, reached_semis, reached_final FROM teams WHERE LOWER(name) = LOWER(?)", (winner_name,)).fetchone()
            if winner_row:
                w = dict(winner_row)
                if not w["reached_quarters"]:
                    conn.execute("UPDATE teams SET reached_quarters = 1 WHERE id = ?", (w["id"],))
                elif not w["reached_semis"]:
                    conn.execute("UPDATE teams SET reached_semis = 1 WHERE id = ?", (w["id"],))
                elif not w["reached_final"]:
                    conn.execute("UPDATE teams SET reached_final = 1 WHERE id = ?", (w["id"],))
                else:
                    conn.execute("UPDATE teams SET won_tournament = 1 WHERE id = ?", (w["id"],))

            conn.execute("UPDATE teams SET status = 'Eliminated' WHERE LOWER(name) = LOWER(?)", (loser_name,))
        _recalculate_all_scores(conn)

    return {"message": "Match result recorded", "home": result["home"], "away": result["away"]}


@admin_router.put("/api/admin/teams/{team_id}", tags=["Admin"])
def override_team(team_id: int, req: TeamOverrideRequest, _auth=Depends(require_admin_auth)):
    """Manually update any combination of a team's stats or status."""
    updates = {}
    bool_fields = {"reached_quarters", "reached_semis", "reached_final", "won_tournament"}
    for field in ("wins", "draws", "losses", "goals_for", "goals_against", "clean_sheets", "reached_quarters", "reached_semis", "reached_final", "won_tournament", "status"):
        val = getattr(req, field)
        if val is not None:
            updates[field] = int(val) if field in bool_fields else val

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [team_id]

    with get_db() as conn:
        result = conn.execute(f"UPDATE teams SET {set_clause} WHERE id = ?", values)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Team not found")
        _recalculate_all_scores(conn)

    return {"message": "Team updated"}


@admin_router.put("/api/admin/users/{user_id}/points", tags=["Admin"])
def override_user_points(user_id: int, req: UserPointsOverrideRequest, _auth=Depends(require_admin_auth)):
    """Manually set a player's total points."""
    with get_db() as conn:
        result = conn.execute("UPDATE users SET total_points = ? WHERE id = ?", (req.total_points, user_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User points updated"}


@admin_router.get("/api/settings", tags=["Admin"])
def get_settings(_auth=Depends(require_admin_auth)):
    """Return all settings."""
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings WHERE key NOT LIKE '%password%'").fetchall()
    return {r["key"]: r["value"] for r in rows}


@admin_router.put("/api/settings/{key}", tags=["Admin"])
def update_setting(key: str, req: SettingUpdate, _auth=Depends(require_admin_auth)):
    """Update a non-password setting."""
    if "password" in key.lower():
        raise HTTPException(status_code=400, detail="Use /api/auth endpoints to manage passwords")
    with get_db() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, req.value))
    return {"message": f"Setting {key} updated"}
