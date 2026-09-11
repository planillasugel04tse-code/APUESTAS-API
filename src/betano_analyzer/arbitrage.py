from __future__ import annotations

import os
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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


# Maximum age of a live odds snapshot before it is considered stale.
# Can be overridden via LIVE_STALE_MINUTES environment variable.
def _live_stale_minutes() -> int:
    try:
        return max(1, int(os.getenv("LIVE_STALE_MINUTES", "15")))
    except (TypeError, ValueError):
        return 15


def _is_live(kickoff: object, now: datetime | None = None, status: object | None = None) -> bool:
    """Prefer the provider/database match state over kickoff-time inference.

    Kickoff is only a fallback for legacy rows where no usable status exists.
    """
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"live", "in_play", "inplay", "started"}:
        return True
    if normalized_status in {"scheduled", "pre_match", "prematch", "upcoming"}:
        return False
    if normalized_status in {"finished", "ended", "cancelled", "canceled", "postponed"}:
        return False

    now = now or datetime.now(timezone.utc)
    try:
        value = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= now
    except (TypeError, ValueError):
        return False


def _market_base(market: object) -> str:
    text = str(market or "").lower()
    for suffix in ("_ft", "_1h", "_2h"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def _selection_key(selection: object) -> str:
    text = str(selection or "").strip().lower()
    return text.split(":", 1)[-1].strip()


def _captured_at(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _is_stale_live(captured_at_value: object, now: datetime, stale_minutes: int) -> bool:
    """Return True if a live odds snapshot is older than the stale threshold."""
    ts = _captured_at(captured_at_value)
    if ts is None:
        return True  # unknown timestamp is treated as stale in live mode
    return (now - ts) > timedelta(minutes=stale_minutes)


def find_arbitrage(
    limit: int = 100,
    *,
    live: bool = False,
    match_id: int | None = None,
) -> list[Arbitrage]:
    """Find arbitrage opportunities from stored odds.

    Live mode behaviour
    -------------------
    When ``live=True``, odds snapshots older than ``LIVE_STALE_MINUTES`` (default 15)
    are excluded. This prevents phantom surebet alerts from stale live prices.
    A cuota live antigua NUNCA se trata como cuota live válida.

    Pre-match behaviour
    -------------------
    Only the latest snapshot per bookmaker/outcome is used so that a previously
    attractive price that has since moved cannot create a phantom arbitrage.
    """
    now = datetime.now(timezone.utc)
    stale_minutes = _live_stale_minutes()

    with connect() as db:
        rows = db.execute(
            """SELECT o.match_id,o.bookmaker,o.market,o.selection,o.line,o.odds,
                      o.captured_at,m.home_team,m.away_team,m.kickoff,m.status
               FROM odds o JOIN matches m ON m.id=o.match_id
               WHERE o.odds > 1
                 AND (? IS NULL OR o.match_id = ?)
               ORDER BY o.captured_at DESC""",
            (match_id, match_id),
        ).fetchall()

    # Keep only the latest snapshot per (match, market, line, bookmaker, outcome).
    # For live mode, also enforce the freshness window.
    latest: dict[tuple[object, str, str, object, str], object] = {}
    for row in rows:
        row_is_live = _is_live(row["kickoff"], now, row["status"])
        if row_is_live != live:
            continue
        # Freshness gate for live odds only
        if live and _is_stale_live(row["captured_at"], now, stale_minutes):
            continue
        outcome = _selection_key(row["selection"])
        key = (
            row["match_id"],
            str(row["market"]).lower(),
            row["line"],
            str(row["bookmaker"]).lower(),
            outcome,
        )
        current = latest.get(key)
        if current is None:
            latest[key] = row
            continue
        current_time = _captured_at(current["captured_at"])
        row_time = _captured_at(row["captured_at"])
        if row_time is not None and (current_time is None or row_time > current_time):
            latest[key] = row

    groups: dict[tuple, list] = defaultdict(list)
    for row in latest.values():
        groups[(row["match_id"], row["market"], row["line"])].append(row)

    result: list[Arbitrage] = []
    for (current_match_id, market, line), quotes in groups.items():
        best: dict[str, tuple[str, float]] = {}
        for row in quotes:
            outcome = _selection_key(row["selection"])
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
