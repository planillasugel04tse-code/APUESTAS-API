from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

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


def find_arbitrage(limit: int = 100) -> list[Arbitrage]:
    with connect() as db:
        rows = db.execute(
            """SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,
                      m.home_team,m.away_team
               FROM odds o JOIN matches m ON m.id=o.match_id
               WHERE o.odds > 1
               ORDER BY o.captured_at DESC"""
        ).fetchall()

    groups = defaultdict(list)
    for row in rows:
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
        elif market in {"spread", "handicap"}:
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
            ))
            if len(result) >= limit:
                break
    return result
