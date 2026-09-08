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


def _is_live(kickoff: object, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    try:
        value = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= now
    except (TypeError, ValueError):
        return False


def _market_base(market: object) -> str:
    """Remove the period suffix from canonical markets (e.g. goals_ft -> goals)."""
    text = str(market or "").lower()
    for suffix in ("_ft", "_1h", "_2h"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def find_arbitrage(limit: int = 100, *, live: bool = False, match_id: int | None = None) -> list[Arbitrage]:
    """Find surebets from stored prices, optionally restricted to one match.

    Pre-match mode only considers fixtures whose kickoff is in the future.
    Live mode only considers fixtures whose kickoff has started. The live
    provider refresh is deliberately handled by the on-demand API endpoint.
    """
    now = datetime.now(timezone.utc)
    with connect() as db:
        rows = db.execute(
            """SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,
                      o.captured_at,m.home_team,m.away_team,m.kickoff
               FROM odds o JOIN matches m ON m.id=o.match_id
               WHERE o.odds > 1
                 AND (? IS NULL OR o.match_id = ?)
               ORDER BY o.captured_at DESC""",
            (match_id, match_id),
        ).fetchall()

    groups = defaultdict(list)
    for row in rows:
        if _is_live(row["kickoff"], now) != live:
            continue
        groups[(row["match_id"], row["market"], row["line"])].append(row)

    result: list[Arbitrage] = []
    for (current_match_id, market, line), quotes in groups.items():
        best: dict[str, tuple[str, float]] = {}
        for row in quotes:
            outcome = row["selection"].split(":", 1)[-1].lower()
            price = float(row["odds"])
            if outcome not in best or price > best[outcome][1]:
                best[outcome] = (row["bookmaker"], price)

        base_market = _market_base(market)
        if base_market == "1x2":
            required = {"home", "draw", "away"}
        elif base_market in {"goals", "corners", "cards"}:
            required = {"over", "under"}
        elif base_market == "btts":
            required = {"yes", "no"}
        elif base_market in {"spread", "handicap", "asian_handicap"}:
            required = {"home", "away"}
        else:
            continue
        if not required.issubset(best):
            continue

        selected = {key: best[key] for key in required}
        implied_sum = sum(1.0 / quote[1] for quote in selected.values())
        if implied_sum < 1.0:
            result.append(
                Arbitrage(
                    match_id=current_match_id,
                    match=f"{quotes[0]['home_team']} vs {quotes[0]['away_team']}",
                    market=market,
                    line=line,
                    outcomes={k: {"bookmaker": v[0], "odds": v[1]} for k, v in selected.items()},
                    implied_sum=implied_sum,
                    profit_margin=(1.0 / implied_sum) - 1.0,
                    mode="live" if live else "pre_match",
                )
            )
            if len(result) >= limit:
                break
    return result


# Register dedicated filters on the existing API router. Live remains manual:
# opening the dashboard or the pre-match filter never calls the odds provider.
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
            sync = await sync_oddspapi_betano_pe(hours=hours, limit_matches=limit_matches, include_live=True, live_only=True)
        except (RuntimeError, ValueError) as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {
            "mode": "live",
            "refreshed_on_demand": True,
            "sync": sync.__dict__,
            "opportunities": [item.__dict__ for item in find_arbitrage(limit, live=True)],
        }

    @_api_router.post("/arbitrage/verify/{match_id}", tags=["arbitrage"])
    async def verify_arbitrage(match_id: int, limit: int = 100):
        """Refresh odds for one event only, then recalculate its surebets."""
        from .oddspapi_io import ODDSPAPI_BETANO_PE, fetch_market_catalog, fetch_odds
        from .ingestion_service import save_odds

        with connect() as db:
            match = db.execute("SELECT id,external_id,kickoff FROM matches WHERE id=?", (match_id,)).fetchone()
        if match is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Partido no encontrado")

        try:
            catalog = await fetch_market_catalog()
            odds = await fetch_odds(str(match["external_id"]), bookmaker=ODDSPAPI_BETANO_PE, market_catalog=catalog)
            _, saved = save_odds(odds)
        except (RuntimeError, ValueError) as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        live = _is_live(match["kickoff"])
        opportunities = find_arbitrage(limit, live=live, match_id=match_id)
        return {
            "mode": "live" if live else "pre_match",
            "match_id": match_id,
            "refreshed_only_this_match": True,
            "odds_seen": len(odds),
            "odds_saved": saved,
            "surebet_confirmed": bool(opportunities),
            "opportunities": [item.__dict__ for item in opportunities],
        }
except ImportError:
    pass
