from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    match_id: int
    match: str
    market: str
    selection: str
    odds: float
    model_probability: float
    implied_probability: float
    edge: float
    confidence: float
    consensus: int
    rating: str


def score_opportunity(*, match_id: int, match: str, market: str, selection: str,
                      odds: float, model_probability: float, consensus: int = 0,
                      confidence: float | None = None) -> Opportunity:
    if odds <= 1:
        raise ValueError("La cuota debe ser mayor que 1")
    implied = 1 / odds
    edge = model_probability - implied
    conf = model_probability if confidence is None else confidence
    if edge >= 0.08 and conf >= 0.72 and consensus >= 3:
        rating = "fuerte"
    elif edge >= 0.04 and conf >= 0.65 and consensus >= 2:
        rating = "interesante"
    else:
        rating = "descartar"
    return Opportunity(match_id, match, market, selection, odds, model_probability,
                       implied, edge, conf, consensus, rating)
