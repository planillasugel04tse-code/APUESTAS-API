from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketAnalysis:
    odds: list[float]
    implied_probabilities: list[float]
    margin: float
    fair_probabilities: list[float]


def analyze_market(odds: list[float]) -> MarketAnalysis:
    if not odds or any(o <= 1 for o in odds):
        raise ValueError("Las cuotas deben ser mayores que 1")

    implied = [1.0 / o for o in odds]
    margin = sum(implied) - 1.0
    fair = [p / sum(implied) for p in implied]
    return MarketAnalysis(odds, implied, margin, fair)
