from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone
import re

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
    """Normalise bookmaker names while preserving the country suffix."""
    return re.sub(r"[^a-z0-9]+", " ", value.strip().lower()).strip()


def _is_allowed_bookmaker(name: str, allowed: set[str] | None) -> bool:
    if allowed is None:
        return True
    return _normalise_bookmaker(name) in allowed


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


def _parse_captured(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def find_arbitrage(
    limit: int = 100,
    bookmakers: list[str] | None = None,
    total_stake: float = 100.0,
    max_age_seconds: int | None = None,
) -> list[Arbitrage]:
    """Find mathematical arbitrage opportunities from stored odds.

    ``bookmakers`` is matched exactly after normalisation, so a generic
    ``bet365`` feed cannot be mistaken for ``Bet365.pe``. ``max_age_seconds``
    optionally rejects stale quotes, which is useful for live betting.
    """
    if total_stake <= 0:
        raise ValueError("total_stake debe ser mayor que 0")
    if max_age_seconds is not None and max_age_seconds < 0:
        raise ValueError("max_age_seconds no puede ser negativo")

    allowed = None
    if bookmakers:
        allowed = {_normalise_bookmaker(item) for item in bookmakers if item.strip()}
        if not allowed:
            raise ValueError("bookmakers no puede estar vacío")

    with connect() as db:
        rows = db.execute(
            """SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,
                      o.captured_at,m.home_team,m.away_team
               FROM odds o JOIN matches m ON m.id=o.match_id
               WHERE o.odds > 1
               ORDER BY o.captured_at DESC"""
        ).fetchall()

    now = datetime.now(timezone.utc)
    groups = defaultdict(list)
    for row in rows:
        if not _is_allowed_bookmaker(row["bookmaker"], allowed):
            continue
        if max_age_seconds is not None:
            captured = _parse_captured(row["captured_at"])
            if captured is None or (now - captured).total_seconds() > max_age_seconds:
                continue
        groups[(row["match_id"], row["market"], row["line"])].append(row)

    result: list[Arbitrage] = []
    for (match_id, market, line), quotes in groups.items():
        required = _required_outcomes(market)
        if not required:
            continue

        # Keep only the newest quote for each bookmaker/outcome/line. This
        # prevents a stale historical price being paired with a fresh price.
        latest: dict[tuple[str, str], object] = {}
        for row in quotes:
            outcome = row["selection"].split(":", 1)[-1].strip().lower()
            if outcome not in required:
                continue
            key = (_normalise_bookmaker(row["bookmaker"]), outcome)
            if key not in latest:
                latest[key] = row

        by_outcome: dict[str, dict[str, tuple[str, float]]] = defaultdict(dict)
        for row in latest.values():
            outcome = row["selection"].split(":", 1)[-1].strip().lower()
            bookmaker = row["bookmaker"]
            price = float(row["odds"])
            key = _normalise_bookmaker(bookmaker)
            previous = by_outcome[outcome].get(key)
            if previous is None or price > previous[1]:
                by_outcome[outcome][key] = (bookmaker, price)

        if not all(outcome in by_outcome for outcome in required):
            continue

        selected = {
            outcome: max(by_outcome[outcome].values(), key=lambda quote: quote[1])
            for outcome in required
        }
        implied_sum = sum(1.0 / quote[1] for quote in selected.values())
        if implied_sum >= 1.0:
            continue

        guaranteed_return = total_stake / implied_sum
        guaranteed_profit = guaranteed_return - total_stake
        raw_stakes = {
            outcome: total_stake * (1.0 / quote[1]) / implied_sum
            for outcome, quote in selected.items()
        }
        rounded = {outcome: round(stake, 2) for outcome, stake in raw_stakes.items()}
        if rounded:
            first = next(iter(rounded))
            rounded[first] = round(total_stake - sum(v for k, v in rounded.items() if k != first), 2)
        outcomes = {
            outcome: {
                "bookmaker": quote[0],
                "odds": quote[1],
                "stake": rounded[outcome],
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
