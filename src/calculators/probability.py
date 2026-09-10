import math
from scipy.stats import poisson
from typing import Dict, Any

class ProbabilityCalculator:
    """Calculates probabilities using Statistical and Mathematical models"""

    @staticmethod
    def calculate_fair_odds(probability: float) -> float:
        """Calculate fair odds (1 / P) without bookmaker margin"""
        if probability <= 0.0:
            return 999.0
        return round(1.0 / probability, 2)

    @staticmethod
    def poisson_goals_matrix(home_exp_goals: float, away_exp_goals: float, max_goals: int = 6) -> Dict[str, Any]:
        """
        Build a goal matrix (0-6 goals each team) using Poisson distribution
        and compute match outcome probabilities (Home, Draw, Away, Over/Under 2.5).
        """
        home_probs = [poisson.pmf(i, home_exp_goals) for i in range(max_goals + 1)]
        away_probs = [poisson.pmf(j, away_exp_goals) for j in range(max_goals + 1)]

        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0
        over_25_prob = 0.0
        under_25_prob = 0.0

        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = home_probs[i] * away_probs[j]
                if i > j:
                    home_win_prob += p
                elif i == j:
                    draw_prob += p
                else:
                    away_win_prob += p

                if (i + j) > 2.5:
                    over_25_prob += p
                else:
                    under_25_prob += p

        return {
            "home_win": round(home_win_prob, 4),
            "draw": round(draw_prob, 4),
            "away_win": round(away_win_prob, 4),
            "over_2.5": round(over_25_prob, 4),
            "under_2.5": round(under_25_prob, 4),
            "fair_odds": {
                "home_win": ProbabilityCalculator.calculate_fair_odds(home_win_prob),
                "draw": ProbabilityCalculator.calculate_fair_odds(draw_prob),
                "away_win": ProbabilityCalculator.calculate_fair_odds(away_win_prob),
                "over_2.5": ProbabilityCalculator.calculate_fair_odds(over_25_prob),
                "under_2.5": ProbabilityCalculator.calculate_fair_odds(under_25_prob)
            }
        }

    @staticmethod
    def poisson_corners_probability(expected_corners: float, line: float) -> Dict[str, Any]:
        """
        Calculate Over/Under probability for corners using cumulative Poisson distribution.
        """
        under_prob = float(poisson.cdf(math.floor(line), expected_corners))
        over_prob = 1.0 - under_prob

        return {
            "expected_corners": expected_corners,
            "line": line,
            "under_prob": round(under_prob, 4),
            "over_prob": round(over_prob, 4),
            "fair_under_odds": ProbabilityCalculator.calculate_fair_odds(under_prob),
            "fair_over_odds": ProbabilityCalculator.calculate_fair_odds(over_prob)
        }
