from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .oddspapi_odds import cache_info, get_odds

router = APIRouter(prefix="/api/v1/oddspapi", tags=["oddspapi-odds"])


@router.get("/odds/{fixture_id}")
async def oddspapi_odds(
    fixture_id: str,
    bookmakers: str | None = Query(default=None, description="Slugs separados por comas"),
    language: str = "es",
    odds_format: str = Query(default="decimal", alias="oddsFormat"),
    verbosity: int = Query(default=3, ge=1, le=10),
    cache_seconds: int = Query(default=0, ge=0, le=300),
    force_refresh: bool = False,
):
    """Get several bookmakers for one fixture with optional local caching."""
    try:
        payload = await get_odds(
            fixture_id,
            bookmakers=bookmakers,
            language=language,
            odds_format=odds_format,
            verbosity=verbosity,
            cache_seconds=cache_seconds,
            force_refresh=force_refresh,
        )
        return payload
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cache")
def oddspapi_cache():
    return cache_info()
