from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CLVSignal:
    entry_odds: float
    closing_odds: float
    clv: float
    direction: str


def calculate_clv(entry_odds: float, closing_odds: float) -> CLVSignal:
    if entry_odds <= 1 or closing_odds <= 1:
        raise ValueError("Las cuotas deben ser mayores que 1")
    clv = entry_odds / closing_odds - 1.0
    return CLVSignal(
        entry_odds=entry_odds,
        closing_odds=closing_odds,
        clv=clv,
        direction="positive" if clv > 0 else "negative" if clv < 0 else "flat",
    )
