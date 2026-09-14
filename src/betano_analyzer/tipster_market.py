from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import sqlite3

from .db import connect


@dataclass(frozen=True)
class MarketQuote:
    bookmaker: str
    odds: float
    market: str
    selection: str
    line: float | None
    captured_at: str
    age_seconds: float


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _parse_timestamp(value: str) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _age_seconds(value: str, now: datetime) -> float:
    stamp = _parse_timestamp(value)
    if stamp is None:
        return float("inf")
    return max(0.0, (now - stamp).total_seconds())


def best_market_quotes(
    match_id: int,
    market: str,
    selection: str,
    *,
    line: float | None = None,
    max_age_minutes: int = 180,
    bookmakers: list[str] | None = None,
) -> list[MarketQuote]:
    """Return the freshest usable quotes, best first, for one normalized pick.

    The function reads stored odds only. It does not call a bookmaker and does
    not place bets. A caller can request a shorter freshness window for LIVE
    workflows. Exact line matching is used when a line is supplied.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max(1, max_age_minutes))
    clauses = [
        "match_id = ?",
        "LOWER(TRIM(market)) = LOWER(TRIM(?))",
        "LOWER(TRIM(selection)) = LOWER(TRIM(?))",
        "odds > 1",
    ]
    params: list[object] = [match_id, market, selection]
    if line is None:
        clauses.append("line IS NULL")
    else:
        clauses.append("line = ?")
        params.append(line)
    if bookmakers:
        placeholders = ",".join("?" for _ in bookmakers)
        clauses.append(f"bookmaker IN ({placeholders})")
        params.extend(bookmakers)

    query = f"SELECT bookmaker, odds, market, selection, line, captured_at FROM odds WHERE {' AND '.join(clauses)} ORDER BY odds DESC, captured_at DESC"
    try:
        with connect() as db:
            rows = db.execute(query, params).fetchall()
    except sqlite3.Error:
        return []

    result: list[MarketQuote] = []
    seen: set[str] = set()
    for row in rows:
        captured = str(row["captured_at"])
        stamp = _parse_timestamp(captured)
        if stamp is None or stamp < cutoff:
            continue
        bookmaker = str(row["bookmaker"])
        key = bookmaker.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(
            MarketQuote(
                bookmaker=bookmaker,
                odds=float(row["odds"]),
                market=str(row["market"]),
                selection=str(row["selection"]),
                line=float(row["line"]) if row["line"] is not None else None,
                captured_at=captured,
                age_seconds=_age_seconds(captured, now),
            )
        )
    return result


def best_market_quote(*args, **kwargs) -> dict[str, object] | None:
    quotes = best_market_quotes(*args, **kwargs)
    return asdict(quotes[0]) if quotes else None
