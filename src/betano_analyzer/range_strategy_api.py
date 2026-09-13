from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .range_strategy import analyze_range

router = APIRouter(prefix="/api/v1/range-strategy", tags=["range-strategy"])


@router.get("")
def range_strategy(
    market: str = Query(..., description="goals or corners"),
    lines: str = Query(..., description="Comma-separated lines, e.g. 1.5,2.5,3.5"),
    expected_total: float = Query(..., ge=0),
    minimum_gap: float = Query(default=0.5, ge=0),
):
    try:
        parsed_lines = [float(item.strip()) for item in lines.split(",") if item.strip()]
        if len(parsed_lines) < 2:
            raise ValueError("at least two lines are required")
        gaps = analyze_range(market, parsed_lines, expected_total, minimum_gap=minimum_gap)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "market": market.strip().lower(),
        "expected_total": expected_total,
        "lines": sorted(set(parsed_lines)),
        "gaps": [gap.__dict__ for gap in gaps],
        "analysis_only": True,
        "note": "Range Strategy is an analytical signal; it does not place bets.",
    }
