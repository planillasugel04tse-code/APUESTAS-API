from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FairMarket:
    market: str
    line: float | None
    outcomes: tuple[str, ...]
    fair_probabilities: tuple[float, ...]
    fair_odds: tuple[float, ...]
    overround: float


@dataclass(frozen=True)
class ValueSignal:
    outcome: str
    offered_odds: float
    fair_probability: float
    fair_odds: float
    edge: float
    ev: float
    rating: str


def devig(probabilities: Iterable[float]) -> tuple[float, ...]:
    values = tuple(p for p in probabilities if p > 0)
    total = sum(values)
    if not values or total <= 0:
        return tuple()
    return tuple(p / total for p in values)


def fair_market(outcomes: Iterable[str], odds: Iterable[float], market: str = "", line: float | None = None) -> FairMarket:
    names = tuple(outcomes)
    prices = tuple(float(o) for o in odds)
    if len(names) != len(prices) or not names:
        raise ValueError("outcomes y odds deben tener la misma longitud")
    if any(o <= 1 for o in prices):
        raise ValueError("todas las cuotas deben ser mayores que 1")
    implied = tuple(1 / o for o in prices)
    overround = sum(implied) - 1
    fair_probs = devig(implied)
    fair_odds = tuple(1 / p for p in fair_probs)
    return FairMarket(market, line, names, fair_probs, fair_odds, overround)


def value_signal(offered_odds: float, fair_probability: float, outcome: str = "") -> ValueSignal:
    if offered_odds <= 1 or not 0 < fair_probability < 1:
        raise ValueError("cuota o probabilidad inválida")
    fair_odds = 1 / fair_probability
    edge = offered_odds / fair_odds - 1
    ev = fair_probability * offered_odds - 1
    if edge >= 0.08:
        rating = "fuerte"
    elif edge >= 0.05:
        rating = "interesante"
    elif edge >= 0.03:
        rating = "vigilar"
    else:
        rating = "descartar"
    return ValueSignal(outcome, offered_odds, fair_probability, fair_odds, edge, ev, rating)


def market_value(outcomes: Iterable[str], fair_odds_source: Iterable[float], offered_odds: Iterable[float], market: str = "", line: float | None = None) -> tuple[FairMarket, tuple[ValueSignal, ...]]:
    fair = fair_market(outcomes, fair_odds_source, market, line)
    offered = tuple(float(o) for o in offered_odds)
    if len(offered) != len(fair.outcomes):
        raise ValueError("las cuotas ofrecidas no coinciden con los resultados")
    signals = tuple(value_signal(price, probability, outcome) for outcome, price, probability in zip(fair.outcomes, offered, fair.fair_probabilities))
    return fair, signals
