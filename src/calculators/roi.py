from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any

class ROICalculator:
    """High-precision Decimal calculations for ROI and Expected Value (EV)"""

    @staticmethod
    def calculate_surebet_roi(inverse_sum: float) -> float:
        """
        Calculate surebet ROI percentage from inverse odds sum.
        roi = ((1 / inverse_sum) - 1) * 100
        """
        if inverse_sum <= 0:
            return 0.0
        
        inv_dec = Decimal(str(inverse_sum))
        roi_dec = ((Decimal('1') / inv_dec) - Decimal('1')) * Decimal('100')
        return float(roi_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    @staticmethod
    def calculate_value_edge(model_probability: float, bookmaker_odds: float) -> Dict[str, Any]:
        """
        Calculate edge percentage and EV for a value bet.
        edge = (model_probability * bookmaker_odds - 1) * 100
        fair_odds = 1 / model_probability
        """
        if model_probability <= 0 or bookmaker_odds <= 1.0:
            return {"edge_percentage": 0.0, "fair_odds": 999.0, "is_value": False}

        p_dec = Decimal(str(model_probability))
        odds_dec = Decimal(str(bookmaker_odds))
        fair_odds_dec = Decimal('1') / p_dec

        ev_dec = (p_dec * odds_dec - Decimal('1')) * Decimal('100')
        edge_rounded = float(ev_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        return {
            "edge_percentage": edge_rounded,
            "fair_odds": float(fair_odds_dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "bookmaker_odds": float(odds_dec),
            "model_probability": float(p_dec),
            "is_value": edge_rounded > 0
        }
