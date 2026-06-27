import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from database import get_db
from models import UserCreate, UserResponse
from helpers import require_site_auth, _row_to_team

users_router = APIRouter()


@users_router.get("/api/users", response_model=List[UserResponse], tags=["Users"])
def list_users(_auth=Depends(require_site_auth)):
    """List all registered players."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin, total_points FROM users ORDER BY username"
        ).fetchall()
    return [_row_to_team(r) for r in rows]


@users_router.post("/api/users", response_model=UserResponse, status_code=201, tags=["Users"])
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


@users_router.get("/api/users/{user_id}", response_model=UserResponse, tags=["Users"])
def get_user(user_id: int, _auth=Depends(require_site_auth)):
    """Get a single player's details."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, total_points FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_team(row)
