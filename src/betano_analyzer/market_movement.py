from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .db import connect


@dataclass(frozen=True)
class Movement:
    match_id: int
    bookmaker: str
    market: str
    selection: str
    previous_odds: float
    current_odds: float
    change_pct: float
    direction: str
    minutes_between: float
    velocity_pct_hour: float
    signal: str


def _minutes(a: str, b: str) -> float:
    try:
        first = datetime.fromisoformat(a.replace("Z", "+00:00"))
        second = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return max((second - first).total_seconds() / 60.0, 0.0)
    except ValueError:
        return 0.0


def classify(change_pct: float, velocity_pct_hour: float) -> str:
    magnitude = abs(change_pct)
    speed = abs(velocity_pct_hour)
    if magnitude >= 8 or speed >= 20:
        return "anomalous"
    if magnitude >= 3 or speed >= 10:
        return "relevant"
    return "normal"


def compare_snapshots(rows: Iterable[dict]) -> list[Movement]:
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["match_id"], row["bookmaker"], row["market"], row["selection"])
        grouped.setdefault(key, []).append(row)

    result: list[Movement] = []
    for key, items in grouped.items():
        items.sort(key=lambda x: x["captured_at"])
        if len(items) < 2:
            continue
        prev, cur = items[-2], items[-1]
        if prev["odds"] <= 1 or cur["odds"] <= 1:
            continue
        minutes = _minutes(prev["captured_at"], cur["captured_at"])
        change = (cur["odds"] / prev["odds"] - 1) * 100
        velocity = change * 60 / minutes if minutes > 0 else 0.0
        direction = "up" if change > 0.05 else "down" if change < -0.05 else "stable"
        result.append(Movement(*key, prev["odds"], cur["odds"], change, direction, minutes, velocity, classify(change, velocity)))
    return result


def latest_movements(match_id: int | None = None) -> list[Movement]:
    with connect() as db:
        where = "WHERE o.match_id=?" if match_id is not None else ""
        params = (match_id,) if match_id is not None else ()
        rows = db.execute(
            f"""
            SELECT o.match_id, o.bookmaker, o.market, o.selection, o.odds, o.captured_at
            FROM odds o {where}
            ORDER BY o.match_id, o.bookmaker, o.market, o.selection, o.captured_at
            """,
            params,
        ).fetchall()
    return compare_snapshots([dict(row) for row in rows])
