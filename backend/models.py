from pydantic import BaseModel, field_validator
from typing import Optional


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class SiteAuthRequest(BaseModel):
    password: str


class AdminAuthRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    total_points: int


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TeamResponse(BaseModel):
    id: int
    name: str
    status: str
    owner_id: Optional[int]
    owner_username: Optional[str]
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    clean_sheets: int
    points_earned: int
    reached_quarters: bool
    reached_semis: bool
    reached_final: bool
    won_tournament: bool


class TeamOverrideRequest(BaseModel):
    """All fields optional — only provided fields are updated."""
    wins: Optional[int] = None
    draws: Optional[int] = None
    losses: Optional[int] = None
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    clean_sheets: Optional[int] = None
    reached_quarters: Optional[bool] = None
    reached_semis: Optional[bool] = None
    reached_final: Optional[bool] = None
    won_tournament: Optional[bool] = None
    status: Optional[str] = None


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    total_points: int
    team_count: int


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

class TradeCreate(BaseModel):
    proposer_id: int
    team_offered_id: int
    team_requested_id: int


class TradeRespond(BaseModel):
    user_id: int
    action: str  # "accept" or "reject"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("accept", "reject"):
            raise ValueError("action must be 'accept' or 'reject'")
        return v


class TradeResponse(BaseModel):
    id: int
    proposer_id: int
    proposer_username: str
    receiver_id: int
    receiver_username: str
    team_offered_id: int
    team_offered_name: str
    team_requested_id: int
    team_requested_name: str
    status: str
    created_at: str


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class ParseStandingsRequest(BaseModel):
    raw_text: str


class MatchResultRequest(BaseModel):
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    is_knockout: bool = False
    # For penalty shootouts: specify the winner even though goals are equal
    winner_team: Optional[str] = None


class UserPointsOverrideRequest(BaseModel):
    total_points: int


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class SettingUpdate(BaseModel):
    value: str
