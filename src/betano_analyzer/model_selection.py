from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSelection:
    probability: float
    fair_odds: float
    edge: float
    expected_value: float
    usable: bool
    reason: str


def evaluate_model_probability(
    probability: float,
    offered_odds: float,
    *,
    min_probability: float = 0.50,
    min_edge: float = 0.03,
) -> ModelSelection:
    """Evaluate a model probability without turning it into a forced bet.

    Model output is only an additional signal. A price is considered usable
    when the probability is valid, the offered odds are valid, and the model
    clears conservative probability/edge gates.
    """
    if not 0 < probability < 1:
        raise ValueError("probability must be between 0 and 1")
    if offered_odds <= 1:
        raise ValueError("offered_odds must be greater than 1")
    if not 0 < min_probability < 1:
        raise ValueError("min_probability must be between 0 and 1")
    if min_edge < 0:
        raise ValueError("min_edge must be non-negative")

    fair_odds = 1.0 / probability
    edge = offered_odds / fair_odds - 1.0
    ev = probability * offered_odds - 1.0
    usable = probability >= min_probability and edge >= min_edge
    reason = "model_value" if usable else "insufficient_model_edge"
    return ModelSelection(
        probability=round(probability, 8),
        fair_odds=round(fair_odds, 8),
        edge=round(edge, 8),
        expected_value=round(ev, 8),
        usable=usable,
        reason=reason,
    )
