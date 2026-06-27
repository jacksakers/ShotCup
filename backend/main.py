import os
import sqlite3
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import get_db, init_db
from models import (
    AdminAuthRequest,
    SiteAuthRequest,
    TokenResponse
)
from helpers import (
    _hash_password,
    _verify_password,
    _create_token
)

# Import modular routers
from routes_users import users_router
from routes_teams import teams_router
from routes_leaderboard import leaderboard_router
from trades import trades_router
from routes_admin import admin_router

load_dotenv()


# ---------------------------------------------------------------------------
# Startup / lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    _sync_passwords_from_env()
    yield


def _sync_passwords_from_env() -> None:
    """Hash passwords from .env and upsert them into the settings table."""
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

# Include modular routers
app.include_router(users_router)
app.include_router(teams_router)
app.include_router(leaderboard_router)
app.include_router(trades_router)
app.include_router(admin_router)


# ---------------------------------------------------------------------------
# Auth routes
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
