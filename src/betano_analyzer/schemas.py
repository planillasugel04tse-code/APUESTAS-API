from __future__ import annotations

from pydantic import BaseModel, Field


class MatchCreate(BaseModel):
    external_id: str | None = None
    competition: str
    home_team: str
    away_team: str
    kickoff: str
    status: str = "scheduled"


class TipsterCreate(BaseModel):
    name: str
    source: str | None = None
    country: str | None = None
    language: str | None = None
    active: bool = True


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
    probability: float | None = Field(default=None, ge=0, le=1)
    probability_source: str | None = None


class OddsCreate(BaseModel):
    match_id: int
    bookmaker: str
    market: str
    selection: str
    odds: float = Field(gt=1)
    captured_at: str | None = None


class BetCreate(BaseModel):
    match_id: int
    pick_id: int | None = None
    selection: str
    odds: float = Field(gt=1)
    stake: float = Field(gt=0)
    result: str = "pending"
    cashout: float | None = Field(default=None, ge=0)
    placed_at: str


class BetSettle(BaseModel):
    result: str = Field(pattern="^(won|lost|pending|push|cashout)$")
    cashout: float | None = Field(default=None, ge=0)
    settled_at: str | None = None


class PickResultCreate(BaseModel):
    result: str = Field(pattern="^(won|lost|push|void)$")
    settled_at: str | None = None
    actual_odds: float | None = Field(default=None, gt=1)
    notes: str | None = None
