from __future__ import annotations

from dataclasses import dataclass

from .probability_fusion import fuse_probabilities


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
    probability_source: str = "model"


def score_opportunity(*, match_id: int, match: str, market: str, selection: str,
                      odds: float, model_probability: float, consensus: int = 0,
                      confidence: float | None = None,
                      market_probability: float | None = None,
                      model_probabilities: list[float] | None = None) -> Opportunity:
    """Score a candidate using a fused probability and conservative gates."""
    if odds <= 1:
        raise ValueError("La cuota debe ser mayor que 1")
    probabilities = model_probabilities or [model_probability]
    fusion = fuse_probabilities(
        probabilities,
        market_probability=market_probability,
        offered_odds=odds,
        min_probability=0.50,
        min_edge=0.03,
    )
    probability = fusion.probability
    implied = 1 / odds
    edge = probability - implied
    conf = fusion.confidence if confidence is None else min(confidence, fusion.confidence)
    if edge >= 0.08 and conf >= 0.72 and consensus >= 3:
        rating = "fuerte"
    elif edge >= 0.04 and conf >= 0.65 and consensus >= 2:
        rating = "interesante"
    else:
        rating = "descartar"
    return Opportunity(match_id, match, market, selection, odds, probability,
                       implied, edge, conf, consensus, rating,
                       "+".join(fusion.sources))
