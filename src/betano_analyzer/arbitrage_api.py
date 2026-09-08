from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .arbitrage import find_arbitrage
from .sync_service import sync_oddspapi_betano_pe

router = APIRouter(prefix="/api/v1/arbitrage", tags=["arbitrage"])


@router.get("/pre-match")
def pre_match(limit: int = Query(default=100, ge=1, le=500)):
    return {
        "mode": "pre_match",
        "refresh": "stored_odds_only",
        "opportunities": [item.__dict__ for item in find_arbitrage(limit, live=False)],
    }


@router.post("/live")
async def live(limit: int = Query(default=100, ge=1, le=500), hours: int = Query(default=1, ge=1, le=2), limit_matches: int = Query(default=20, ge=1, le=20)):
    """Refresh live odds only when the user explicitly clicks the live radar."""
    try:
        sync = await sync_oddspapi_betano_pe(
            hours=hours,
            limit_matches=limit_matches,
            include_live=True,
            live_only=True,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "mode": "live",
        "refreshed_on_demand": True,
        "sync": sync.__dict__,
        "opportunities": [item.__dict__ for item in find_arbitrage(limit, live=True)],
    }
