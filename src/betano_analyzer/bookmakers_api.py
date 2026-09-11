from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .bookmakers import available_bookmakers, peru_bookmaker_catalog, peru_bookmakers, selected_bookmakers

router = APIRouter(prefix="/api/v1/bookmakers", tags=["bookmakers"])


@router.get("")
async def bookmakers():
    try:
        return {"bookmakers": await available_bookmakers()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selected")
async def bookmakers_selected():
    try:
        return {"bookmakers": await selected_bookmakers()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/peru")
async def bookmakers_peru():
    try:
        return await peru_bookmaker_catalog()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/peru/names")
async def bookmakers_peru_names():
    try:
        return {"bookmakers": await peru_bookmakers()}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
