from typing import Dict, List
from decimal import Decimal, ROUND_HALF_UP

class OddsNormalizer:
    """Normalizes odds formats, probabilities, and market keys"""

    @staticmethod
    def decimal_to_implied_probability(decimal_odds: float) -> float:
        """Convert decimal odds to raw implied probability (1 / odds)"""
        if decimal_odds <= 1.0:
            return 1.0
        return 1.0 / decimal_odds

    @staticmethod
    def calculate_overround(odds_list: List[float]) -> float:
        """
        Calculate total market overround / margin.
        inverse_sum = sum(1 / odds)
        """
        if not odds_list:
            return 0.0
        return sum(1.0 / o for o in odds_list if o > 1.0)

    @staticmethod
    def remove_margin_proportional(odds_list: List[float]) -> List[float]:
        """
        Remove bookmaker overround proportionally to get fair probabilities.
        Returns list of fair probabilities summing to 1.0.
        """
        raw_probs = [OddsNormalizer.decimal_to_implied_probability(o) for o in odds_list]
        total_prob = sum(raw_probs)
        if total_prob <= 0:
            return [1.0 / len(odds_list)] * len(odds_list)
        return [p / total_prob for p in raw_probs]

    @staticmethod
    def american_to_decimal(american_odds: int) -> float:
        """Convert American odds (+150, -110) to Decimal odds"""
        if american_odds > 0:
            return (american_odds / 100.0) + 1.0
        elif american_odds < 0:
            return (100.0 / abs(american_odds)) + 1.0
        return 1.0

    @staticmethod
    def round_decimal(value: float, decimal_places: int = 2) -> Decimal:
        """High-precision Decimal rounding"""
        d = Decimal(str(value))
        return d.quantize(Decimal(10) ** -decimal_places, rounding=ROUND_HALF_UP)
