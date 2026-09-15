from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .oddspapi_history import hydrate_match_history
from .statistical_engine import TeamMatch, build_report, probability_for_selection, serialize_report
from .team_statistics import build_match_probability, build_team_report, record_history

router = APIRouter(prefix="/api/v1/statistics", tags=["statistics"])


class MatchHistoryItem(BaseModel):
    goals_for: int = Field(ge=0)
    goals_against: int = Field(ge=0)
    home: bool = True


class StatisticsRequest(BaseModel):
    history: list[MatchHistoryItem] = Field(default_factory=list, max_length=100)
    market: str | None = None
    selection: str | None = None
    min_sample: int = Field(default=5, ge=1, le=100)


class TeamHistoryItem(BaseModel):
    team: str = Field(min_length=1, max_length=120)
    opponent: str = Field(min_length=1, max_length=120)
    goals_for: int = Field(ge=0)
    goals_against: int = Field(ge=0)
    is_home: bool = True
    played_at: str | None = None
    external_match_id: str | None = None


class TeamHistoryRequest(BaseModel):
    history: list[TeamHistoryItem] = Field(default_factory=list, max_length=500)
    source: str = Field(default="supplied", min_length=1, max_length=80)


@router.post("/analyze")
def analyze_statistics(payload: StatisticsRequest) -> dict[str, Any]:
    report = build_report(
        [TeamMatch(item.goals_for, item.goals_against, item.home) for item in payload.history],
        min_sample=payload.min_sample,
    )
    probability = None
    if payload.market and payload.selection:
        probability = probability_for_selection(report, payload.market, payload.selection)
    return {
        "report": serialize_report(report),
        "selection_probability": probability,
        "decision": "USE_IN_VALUE_ANALYSIS" if probability is not None else "DATOS_INSUFICIENTES",
        "source": "supplied_match_history",
        "no_invention": True,
    }


@router.post("/history")
def ingest_team_history(payload: TeamHistoryRequest) -> dict[str, Any]:
    inserted = record_history([item.model_dump() for item in payload.history], source=payload.source)
    return {"inserted": inserted, "received": len(payload.history), "source": payload.source, "no_invention": True}


@router.get("/team/{team}")
def team_statistics(team: str, limit: int = 20, min_sample: int = 5) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    min_sample = max(1, min(min_sample, 100))
    return {"team": team, "report": serialize_report(build_team_report(team, limit=limit, min_sample=min_sample)), "source": "stored_team_match_history", "no_invention": True}


@router.get("/match")
def match_statistics(home_team: str, away_team: str, market: str, selection: str, limit: int = 20, min_sample: int = 5) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    min_sample = max(1, min(min_sample, 100))
    return build_match_probability(home_team, away_team, market, selection, limit=limit, min_sample=min_sample)


@router.post("/hydrate/{match_id}")
async def hydrate_statistics(
    match_id: int,
    max_matches: int = Query(default=6, ge=1, le=10),
    max_requests: int = Query(default=16, ge=3, le=30),
) -> dict[str, Any]:
    """Import recent finished team results from OddsPapi, within a hard budget."""
    try:
        summary = await hydrate_match_history(match_id, max_matches=max_matches, max_requests=max_requests)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return summary.__dict__
