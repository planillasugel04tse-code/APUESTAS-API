from __future__ import annotations


def expected_value(probability: float, odds: float) -> float:
    """Expected return per unit staked, expressed as a decimal."""
    if not 0 <= probability <= 1:
        raise ValueError("La probabilidad debe estar entre 0 y 1")
    if odds <= 1:
        raise ValueError("La cuota debe ser mayor que 1")
    return round(probability * odds - 1.0, 12)


def implied_probability(odds: float) -> float:
    if odds <= 1:
        raise ValueError("La cuota debe ser mayor que 1")
    return 1.0 / odds
