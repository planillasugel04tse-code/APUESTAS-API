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
    total_stake: float = 100.0
    guaranteed_return: float = 0.0
    guaranteed_profit: float = 0.0


def _normalise_bookmaker(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _is_allowed_bookmaker(name: str, allowed: set[str] | None) -> bool:
    if allowed is None:
        return True
    normalised = _normalise_bookmaker(name)
    return any(alias in normalised for alias in allowed)


def _required_outcomes(market: str) -> set[str] | None:
    if market == "1x2":
        return {"home", "draw", "away"}
    if market in {"goals", "corners"}:
        return {"over", "under"}
    if market == "btts":
        return {"yes", "no"}
    if market in {"spread", "handicap"}:
        return {"home", "away"}
    return None


def find_arbitrage(
    limit: int = 100,
    bookmakers: list[str] | None = None,
    total_stake: float = 100.0,
) -> list[Arbitrage]:
    """Find mathematical arbitrage opportunities from the latest stored odds.

    When ``bookmakers`` is supplied, every selected outcome must come from one
    of those bookmakers and the same bookmaker is not reused for two outcomes.
    This is useful for the initial Betano PE + Apuesta Total setup.
    """
    if total_stake <= 0:
        raise ValueError("total_stake debe ser mayor que 0")

    allowed = None
    if bookmakers:
        allowed = {_normalise_bookmaker(item) for item in bookmakers if item.strip()}
        if not allowed:
            raise ValueError("bookmakers no puede estar vacío")

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
        if _is_allowed_bookmaker(row["bookmaker"], allowed):
            groups[(row["match_id"], row["market"], row["line"])].append(row)

    result: list[Arbitrage] = []
    for (match_id, market, line), quotes in groups.items():
        required = _required_outcomes(market)
        if not required:
            continue

        # Keep the best quote per outcome/bookmaker, then enumerate the small
        # set of bookmaker assignments so outcomes use distinct houses.
        by_outcome: dict[str, dict[str, tuple[str, float]]] = defaultdict(dict)
        for row in quotes:
            outcome = row["selection"].split(":", 1)[-1].strip().lower()
            if outcome not in required:
                continue
            bookmaker = row["bookmaker"]
            price = float(row["odds"])
            key = _normalise_bookmaker(bookmaker)
            previous = by_outcome[outcome].get(key)
            if previous is None or price > previous[1]:
                by_outcome[outcome][key] = (bookmaker, price)

        if not all(outcome in by_outcome for outcome in required):
            continue

        assignments: list[dict[str, tuple[str, float]]] = [{}]
        for outcome in sorted(required):
            next_assignments = []
            for assignment in assignments:
                used = {_normalise_bookmaker(v[0]) for v in assignment.values()}
                for bookmaker_key, quote in by_outcome[outcome].items():
                    if bookmaker_key in used:
                        continue
                    next_assignments.append({**assignment, outcome: quote})
            assignments = next_assignments
            if not assignments:
                break

        for selected in assignments:
            implied_sum = sum(1.0 / quote[1] for quote in selected.values())
            if implied_sum >= 1.0:
                continue

            guaranteed_return = total_stake / implied_sum
            guaranteed_profit = guaranteed_return - total_stake
            stakes = {
                outcome: total_stake * (1.0 / quote[1]) / implied_sum
                for outcome, quote in selected.items()
            }
            outcomes = {
                outcome: {
                    "bookmaker": quote[0],
                    "odds": quote[1],
                    "stake": round(stakes[outcome], 2),
                }
                for outcome, quote in selected.items()
            }
            result.append(
                Arbitrage(
                    match_id=match_id,
                    match=f"{quotes[0]['home_team']} vs {quotes[0]['away_team']}",
                    market=market,
                    line=line,
                    outcomes=outcomes,
                    implied_sum=implied_sum,
                    profit_margin=(1.0 / implied_sum) - 1.0,
                    total_stake=total_stake,
                    guaranteed_return=guaranteed_return,
                    guaranteed_profit=guaranteed_profit,
                )
            )
            if len(result) >= limit:
                return result

    return result
