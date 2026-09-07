from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class OddsSnapshot:
    bookmaker: str
    market: str
    selection: str
    odds: float
    captured_at: datetime


@dataclass(frozen=True)
class OddsMovement:
    bookmaker: str
    market: str
    selection: str
    previous_odds: float
    current_odds: float
    absolute_change: float
    percent_change: float
    direction: str
    minutes_elapsed: float
    speed_per_hour: float


def calculate_movement(previous: OddsSnapshot, current: OddsSnapshot) -> OddsMovement | None:
    if previous.odds <= 1 or current.odds <= 1:
        return None
    seconds = (current.captured_at - previous.captured_at).total_seconds()
    if seconds <= 0:
        return None
    absolute = current.odds - previous.odds
    percent = absolute / previous.odds * 100
    direction = "up" if absolute > 0 else "down" if absolute < 0 else "flat"
    hours = seconds / 3600
    return OddsMovement(
        bookmaker=current.bookmaker,
        market=current.market,
        selection=current.selection,
        previous_odds=previous.odds,
        current_odds=current.odds,
        absolute_change=absolute,
        percent_change=percent,
        direction=direction,
        minutes_elapsed=seconds / 60,
        speed_per_hour=percent / hours,
    )


def market_consensus(snapshots: Iterable[OddsSnapshot]) -> dict[tuple[str, str], dict[str, float]]:
    groups: dict[tuple[str, str], list[OddsSnapshot]] = {}
    for row in snapshots:
        groups.setdefault((row.market, row.selection), []).append(row)
    result: dict[tuple[str, str], dict[str, float]] = {}
    for key, rows in groups.items():
        prices = [r.odds for r in rows if r.odds > 1]
        if not prices:
            continue
        result[key] = {
            "bookmakers": float(len(prices)),
            "best_odds": max(prices),
            "average_odds": sum(prices) / len(prices),
            "lowest_odds": min(prices),
        }
    return result


def classify_movement(movement: OddsMovement) -> str:
    magnitude = abs(movement.percent_change)
    if magnitude >= 8 or abs(movement.speed_per_hour) >= 25:
        return "anómalo"
    if magnitude >= 3 or abs(movement.speed_per_hour) >= 10:
        return "relevante"
    return "normal"
