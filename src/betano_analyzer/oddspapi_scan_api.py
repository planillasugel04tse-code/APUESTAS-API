from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .arbitrage import find_arbitrage
from .oddspapi_scanner import scan_oddspapi_catalog

router = APIRouter(prefix="/api/v1/oddspapi", tags=["oddspapi-scan"])


@router.post("/scan")
async def scan(
    deep: bool = Query(default=False),
    max_requests: int = Query(default=40, ge=3, le=200),
):
    try:
        return await scan_oddspapi_catalog(deep=deep, max_requests=max_requests)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/global-scan-help")
def global_scan_help():
    return {
        "message": "El escaneo profundo usa un presupuesto explícito porque sports, bookmakers, markets, tournaments y fixtures son endpoints medidos.",
        "recommended_free_mode": "catalog",
    }


@router.get("/global-surebet")
def global_surebet(limit: int = Query(default=100, ge=1, le=500)):
    opportunities = [item.__dict__ for item in find_arbitrage(limit, live=False)]
    return {
        "mode": "global",
        "scope": "todas las casas presentes en las cuotas almacenadas, sin filtro Perú",
        "opportunities": opportunities,
        "count": len(opportunities),
        "message": "No hay surebets mundiales con la data almacenada actualmente." if not opportunities else "Se encontraron oportunidades con la data mundial almacenada.",
    }


@router.get("/global-live-surebet")
def global_live_surebet(limit: int = Query(default=100, ge=1, le=500)):
    opportunities = [item.__dict__ for item in find_arbitrage(limit, live=True)]
    return {
        "mode": "global_live",
        "scope": "todas las casas presentes en las cuotas live almacenadas, sin filtro Perú",
        "opportunities": opportunities,
        "count": len(opportunities),
        "message": "No hay surebets mundiales LIVE con la data almacenada actualmente." if not opportunities else "Se encontraron oportunidades LIVE mundiales.",
    }
