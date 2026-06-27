from fastapi import APIRouter, Depends
from typing import List

from database import get_db
from models import LeaderboardEntry
from helpers import require_site_auth

leaderboard_router = APIRouter()


@leaderboard_router.get("/api/leaderboard", response_model=List[LeaderboardEntry], tags=["Leaderboard"])
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
