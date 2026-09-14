from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .oddspapi_analysis import analyze_odds_payload
from .oddspapi_odds import get_odds

router = APIRouter(prefix="/api/v1/oddspapi", tags=["oddspapi-analysis"])


class OddsAnalysisRequest(BaseModel):
    fixture_id: str | None = None
    bookmakers: list[str] = Field(default_factory=list)
    execution_bookmakers: list[str] = Field(default_factory=list)
    reference_bookmakers: list[str] = Field(default_factory=lambda: ["pinnacle"])
    bankroll: float = Field(default=100.0, gt=0)
    language: str = "es"
    odds_format: str = "decimal"
    verbosity: int = Field(default=3, ge=1, le=10)
    cache_seconds: int = Field(default=5, ge=0, le=300)
    force_refresh: bool = False
    payload: dict | None = None


@router.post("/analyze")
async def analyze(request: OddsAnalysisRequest):
    """Fetch/analyze one fixture, or analyze an already fetched OddsPapi payload.

    No API key is accepted in the request body; the configured provider key is
    read server-side from ODDSPAPI_KEY.
    """
    payload = request.payload
    if payload is None:
        if not request.fixture_id:
            raise HTTPException(status_code=422, detail="fixture_id es obligatorio cuando payload no está presente")
        try:
            payload = await get_odds(
                request.fixture_id,
                bookmakers=request.bookmakers,
                language=request.language,
                odds_format=request.odds_format,
                verbosity=request.verbosity,
                cache_seconds=request.cache_seconds,
                force_refresh=request.force_refresh,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return analyze_odds_payload(
        payload,
        bankroll=request.bankroll,
        execution_bookmakers=request.execution_bookmakers,
        reference_bookmakers=request.reference_bookmakers,
    )
