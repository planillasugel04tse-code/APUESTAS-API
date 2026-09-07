from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityFusion:
    probability: float
    model_probability: float
    market_probability: float | None
    confidence: float
    sources: tuple[str, ...]
    usable: bool
    reason: str


def fuse_probabilities(
    model_probabilities: list[float],
    *,
    market_probability: float | None = None,
    model_weight: float = 0.60,
    market_weight: float = 0.40,
    min_probability: float = 0.50,
    min_edge: float = 0.03,
    offered_odds: float | None = None,
) -> ProbabilityFusion:
    """Combine model estimates with a de-vig market consensus conservatively.

    The market is treated as a reference, not as ground truth. When no market
    consensus is available, the model remains usable only if it clears the
    probability and price gates. This function never forces a bet.
    """
    if not model_probabilities:
        raise ValueError("model_probabilities must not be empty")
    if any(not 0 < p < 1 for p in model_probabilities):
        raise ValueError("all model probabilities must be between 0 and 1")
    if market_probability is not None and not 0 < market_probability < 1:
        raise ValueError("market_probability must be between 0 and 1")
    if model_weight < 0 or market_weight < 0 or model_weight + market_weight <= 0:
        raise ValueError("weights must be non-negative and have positive total")
    if not 0 < min_probability < 1 or min_edge < 0:
        raise ValueError("invalid probability/edge thresholds")
    if offered_odds is not None and offered_odds <= 1:
        raise ValueError("offered_odds must be greater than 1")

    model_probability = sum(model_probabilities) / len(model_probabilities)
    sources = ["model"]
    if market_probability is None:
        probability = model_probability
    else:
        total_weight = model_weight + market_weight
        probability = (
            model_probability * model_weight + market_probability * market_weight
        ) / total_weight
        sources.append("market_consensus")

    confidence = 1.0 - abs(model_probability - market_probability) if market_probability is not None else 0.70
    confidence = max(0.0, min(1.0, confidence))
    edge = probability * offered_odds - 1.0 if offered_odds is not None else None

    usable = probability >= min_probability and (offered_odds is None or edge >= min_edge)
    if probability < min_probability:
        reason = "insufficient_probability"
    elif offered_odds is not None and edge < min_edge:
        reason = "insufficient_fused_edge"
    else:
        reason = "fused_value"

    return ProbabilityFusion(
        probability=round(probability, 8),
        model_probability=round(model_probability, 8),
        market_probability=round(market_probability, 8) if market_probability is not None else None,
        confidence=round(confidence, 8),
        sources=tuple(sources),
        usable=usable,
        reason=reason,
    )
