from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone

from .db import connect


@dataclass(frozen=True)
class Arbitrage:
    match_id: int
    match: str
    market: str
    line: float | None
    outcomes: dict[str, dict[str, object]]
    implied_sum: float
    profit_margin: float
    mode: str


def find_arbitrage(limit: int = 100, *, live: bool = False) -> list[Arbitrage]:
    """Find surebets from the latest stored prices.

    Pre-match mode uses fixtures whose kickoff is still in the future.
    Live mode uses fixtures whose kickoff has already started. Live refreshes
    are deliberately separate so the API is only called when the user asks
    for the live radar.
    """
    now = datetime.now(timezone.utc)
    with connect() as db:
        rows = db.execute(
            """SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,
                      o.captured_at,m.home_team,m.away_team,m.kickoff
               FROM odds o JOIN matches m ON m.id=o.match_id
               WHERE o.odds > 1
               ORDER BY o.captured_at DESC"""
        ).fetchall()

    groups = defaultdict(list)
    for row in rows:
        try:
            kickoff = datetime.fromisoformat(str(row["kickoff"]).replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            is_live = kickoff <= now
        except (TypeError, ValueError):
            is_live = False
        if is_live != live:
            continue
        groups[(row["match_id"], row["market"], row["line"])].append(row)

    result: list[Arbitrage] = []
    for (match_id, market, line), quotes in groups.items():
        best = {}
        for row in quotes:
            outcome = row["selection"].split(":", 1)[-1].lower()
            price = float(row["odds"])
            if outcome not in best or price > best[outcome][1]:
                best[outcome] = (row["bookmaker"], price)

        if market == "1x2":
            required = {"home", "draw", "away"}
        elif market in {"goals", "corners"}:
            required = {"over", "under"}
        elif market == "btts":
            required = {"yes", "no"}
        elif market in {"spread", "handicap", "asian_handicap"}:
            required = {"home", "away"}
        else:
            continue
        if not required.issubset(best):
            continue

        selected = {key: best[key] for key in required}
        implied_sum = sum(1.0 / quote[1] for quote in selected.values())
        if implied_sum < 1.0:
            result.append(Arbitrage(
                match_id=match_id,
                match=f"{quotes[0]['home_team']} vs {quotes[0]['away_team']}",
                market=market,
                line=line,
                outcomes={k: {"bookmaker": v[0], "odds": v[1]} for k, v in selected.items()},
                implied_sum=implied_sum,
                profit_margin=(1.0 / implied_sum) - 1.0,
                mode="live" if live else "pre_match",
            ))
            if len(result) >= limit:
                break
    return result


# The main API router imports find_arbitrage from this module. Register the two
# dedicated surebet filters on that same router here, avoiding a second router
# and keeping the live refresh explicitly on-demand.
try:
    from .api import router as _api_router

    @_api_router.get("/arbitrage/pre-match", tags=["arbitrage"])
    def pre_match_arbitrage(limit: int = 100):
        return {
            "mode": "pre_match",
            "refresh": "stored_odds_only",
            "opportunities": [item.__dict__ for item in find_arbitrage(limit, live=False)],
        }

    @_api_router.post("/arbitrage/live", tags=["arbitrage"])
    async def live_arbitrage(limit: int = 100, hours: int = 1, limit_matches: int = 20):
        from .sync_service import sync_oddspapi_betano_pe

        try:
            sync = await sync_oddspapi_betano_pe(
                hours=hours,
                limit_matches=limit_matches,
                include_live=True,
                live_only=True,
            )
        except (RuntimeError, ValueError) as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "mode": "live",
            "refreshed_on_demand": True,
            "sync": sync.__dict__,
            "opportunities": [item.__dict__ for item in find_arbitrage(limit, live=True)],
        }
except ImportError:
    # Allows direct module imports/tests without the FastAPI application.
    pass
