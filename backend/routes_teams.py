from fastapi import APIRouter, Depends, HTTPException
from typing import List

from database import get_db
from models import TeamResponse
from helpers import require_site_auth, _row_to_team

teams_router = APIRouter()


@teams_router.get("/api/teams", response_model=List[TeamResponse], tags=["Teams"])
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


@teams_router.get("/api/teams/{team_id}", response_model=TeamResponse, tags=["Teams"])
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
