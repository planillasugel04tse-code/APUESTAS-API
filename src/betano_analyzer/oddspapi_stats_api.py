from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .oddspapi_stats import hydrate_team_history

router = APIRouter(prefix="/api/v1/oddspapi", tags=["oddspapi-stats"])


@router.post("/stats/hydrate/{participant_id}")
async def hydrate_stats(
    participant_id: str,
    limit: int = Query(default=5, ge=1, le=10),
) -> dict:
    """Fetch a small finished-match sample and persist it for local analysis."""
    try:
        return await hydrate_team_history(participant_id=participant_id, limit=limit)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
