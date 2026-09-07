from __future__ import annotations

from pydantic import BaseModel, Field


class MatchCreate(BaseModel):
    external_id: str | None = None
    competition: str
    home_team: str
    away_team: str
    kickoff: str
    status: str = "scheduled"


class PickCreate(BaseModel):
    match_id: int
    tipster_id: int | None = None
    original_market: str
    original_selection: str
    original_odds: float | None = Field(default=None, gt=1)
    conservative_market: str | None = None
    conservative_selection: str | None = None
    conservative_odds: float | None = Field(default=None, gt=1)
    confidence: float | None = Field(default=None, ge=0, le=1)


class BetCreate(BaseModel):
    match_id: int
    pick_id: int | None = None
    selection: str
    odds: float = Field(gt=1)
    stake: float = Field(gt=0)
    result: str = "pending"
    cashout: float | None = Field(default=None, ge=0)
    placed_at: str
