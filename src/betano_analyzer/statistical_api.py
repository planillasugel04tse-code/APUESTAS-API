from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .statistical_engine import TeamMatch, build_report, probability_for_selection, serialize_report

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
