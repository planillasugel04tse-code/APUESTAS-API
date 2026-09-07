from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .analysis.value import expected_value, implied_probability


@dataclass(frozen=True)
class OddsQuote:
    bookmaker: str
    market: str
    selection: str
    odds: float


@dataclass(frozen=True)
class MarketComparison:
    market: str
    selection: str
    best_bookmaker: str
    best_odds: float
    implied_probability: float
    fair_odds: float
    model_probability: float
    edge: float
    expected_value: float


def best_quote(quotes: Iterable[OddsQuote], market: str, selection: str) -> OddsQuote | None:
    candidates = [
        q for q in quotes
        if q.market.strip().lower() == market.strip().lower()
        and q.selection.strip().lower() == selection.strip().lower()
        and q.odds > 1
    ]
    return max(candidates, key=lambda q: q.odds, default=None)


def compare_market(
    quotes: Iterable[OddsQuote],
    market: str,
    selection: str,
    model_probability: float,
) -> MarketComparison | None:
    if not 0 < model_probability < 1:
        raise ValueError("La probabilidad del modelo debe estar entre 0 y 1")
    quote = best_quote(quotes, market, selection)
    if quote is None:
        return None
    fair_odds = 1.0 / model_probability
    implied = implied_probability(quote.odds)
    edge = model_probability - implied
    ev = expected_value(model_probability, quote.odds)
    return MarketComparison(
        market=quote.market,
        selection=quote.selection,
        best_bookmaker=quote.bookmaker,
        best_odds=quote.odds,
        implied_probability=implied,
        fair_odds=fair_odds,
        model_probability=model_probability,
        edge=edge,
        expected_value=ev,
    )
