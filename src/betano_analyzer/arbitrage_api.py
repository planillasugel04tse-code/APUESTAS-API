from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from . import sync_service
from .arbitrage import find_arbitrage
from .oddspapi_global_live import sync_global_live

router = APIRouter(prefix="/api/v1/arbitrage", tags=["arbitrage"])

Scope = Literal["all", "peru", "world"]


def _dedupe_opportunities(opportunities):
    """Collapse duplicate rows representing the same event/market/line/mode.

    Match IDs can differ when the same fixture was ingested more than once.
    Surebet is an event-level opportunity, so the API must expose one card per
    normalized event instead of leaking storage duplicates to the UI.
    """
    unique = {}
    for item in opportunities:
        event = " ".join(str(item.match or "").strip().lower().split())
        market = " ".join(str(item.market or "").strip().lower().split())
        line = "" if item.line is None else str(item.line).strip()
        key = (event, market, line, str(item.mode or "").lower())
        current = unique.get(key)
        if current is None or item.profit_margin > current.profit_margin:
            unique[key] = item
    return sorted(unique.values(), key=lambda x: x.profit_margin, reverse=True)


def _result_payload(mode: str, opportunities, *, scope: str, league: str | None, **extra):
    opportunities = _dedupe_opportunities(opportunities)
    items = [item.__dict__ for item in opportunities]
    leagues = sorted({str(item.competition).strip() for item in opportunities if item.competition})
    return {"mode": mode, "scope": scope, "league": league, "leagues": leagues, "opportunities": items, "count": len(items), **extra}


@router.get("/pre-match")
def pre_match(
    limit: int = Query(default=100, ge=1, le=500),
    scope: Scope = Query(default="all"),
    league: str | None = Query(default=None, max_length=120),
):
    opportunities = find_arbitrage(limit, live=False, scope=scope, league=league)
    return _result_payload("pre_match", opportunities, scope=scope, league=league, refresh="stored_odds_only")


@router.post("/live")
async def live(
    limit: int = Query(default=100, ge=1, le=500),
    hours: int = Query(default=1, ge=1, le=2),
    scope: Scope = Query(default="all"),
    league: str | None = Query(default=None, max_length=120),
):
    """Refresh the live SureBet universe once, then apply the requested scope filter."""
    try:
        sync = await sync_global_live(hours=hours, bookmaker_cap=20)
        refresh_scope = "world_universe"
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    opportunities = find_arbitrage(limit, live=True, scope=scope, league=league)
    return _result_payload(
        "live", opportunities, scope=scope, league=league,
        refreshed_on_demand=True, refresh_scope=refresh_scope, sync=sync.__dict__,
    )


@router.post("/verify/{match_id}")
async def verify(
    match_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    scope: Scope = Query(default="all"),
    league: str | None = Query(default=None, max_length=120),
):
    """Refresh and recalculate one fixture before treating a surebet as confirmed."""
    try:
        sync = await sync_service.verify_oddspapi_betano_pe_match(match_id)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503 if isinstance(exc, RuntimeError) else 404, detail=str(exc)) from exc
    opportunities = find_arbitrage(limit, live=True, match_id=match_id, scope=scope, league=league)
    if not opportunities:
        opportunities = find_arbitrage(limit, live=False, match_id=match_id, scope=scope, league=league)
    return _result_payload(
        "verified", opportunities, scope=scope, league=league, match_id=match_id,
        surebet_confirmed=bool(opportunities), odds_seen=sync.odds_seen, odds_saved=sync.odds_saved,
    )
