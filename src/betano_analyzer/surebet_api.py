from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .arbitrage import find_arbitrage

router = APIRouter(prefix="/api/v1")


@router.get("/surebets")
def surebets(
    bookmakers: str = Query(
        default="Betano.pe,ApuestaTotal.pe,Bet365.pe,Betsafe.pe",
        description=(
            "Casas peruanas a comparar, separadas por coma. "
            "El identificador regional debe coincidir exactamente con los datos almacenados."
        ),
    ),
    total_stake: float = Query(default=100.0, gt=0),
    limit: int = Query(default=50, ge=1, le=500),
):
    books = [item.strip() for item in bookmakers.split(",") if item.strip()]
    if len(books) < 2:
        raise HTTPException(status_code=400, detail="Indica al menos dos casas de apuestas")

    try:
        opportunities = find_arbitrage(
            limit=limit,
            bookmakers=books,
            total_stake=total_stake,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "bookmakers": books,
        "total_stake": total_stake,
        "count": len(opportunities),
        "opportunities": [item.__dict__ for item in opportunities],
    }
