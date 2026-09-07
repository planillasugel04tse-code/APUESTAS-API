from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .oddspapi_io import fetch_account
from .sync_service import sync_oddspapi_betano_pe

router = APIRouter(prefix="/api/v1/oddspapi", tags=["oddspapi"])


@router.get("/account")
async def oddspapi_account():
    """Return OddsPapi account/quota state without consuming quota."""
    try:
        return await fetch_account()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sync")
async def sync_betano_pe(
    hours: int = Query(default=48, ge=1, le=48),
    limit_matches: int = Query(default=20, ge=1, le=50),
    include_live: bool = False,
):
    try:
        summary = await sync_oddspapi_betano_pe(
            hours=hours,
            limit_matches=limit_matches,
            include_live=include_live,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return summary.__dict__
