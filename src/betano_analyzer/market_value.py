from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class MarketValue:
    match_id: int
    bookmaker: str
    market: str
    line: float | None
    selection: str
    offered_odds: float
    fair_probability: float
    fair_odds: float
    edge: float
    ev: float
    overround: float
    rating: str


def _rating(edge: float) -> str:
    if edge >= 0.08:
        return "fuerte"
    if edge >= 0.05:
        return "interesante"
    if edge >= 0.03:
        return "vigilar"
    return "descartar"


def _fair(prices: list[float]) -> tuple[list[float], float]:
    implied = [1.0 / price for price in prices if price > 1]
    total = sum(implied)
    if not implied or total <= 0:
        return [], 0.0
    return [p / total for p in implied], total - 1.0


def scan_market(rows: Iterable[dict]) -> list[MarketValue]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        if float(row["odds"]) > 1:
            grouped[(row["match_id"], row["bookmaker"], row["market"], row.get("line"))].append(row)

    results: list[MarketValue] = []
    for (match_id, bookmaker, market, line), items in grouped.items():
        fair_probs, overround = _fair([float(item["odds"]) for item in items])
        if len(fair_probs) != len(items):
            continue
        for item, probability in zip(items, fair_probs):
            offered = float(item["odds"])
            fair_odds = 1.0 / probability
            edge = offered / fair_odds - 1.0
            results.append(MarketValue(match_id, bookmaker, market, line, item["selection"], offered,
                                       probability, fair_odds, edge, probability * offered - 1.0,
                                       overround, _rating(edge)))
    return results
