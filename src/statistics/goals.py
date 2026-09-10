import numpy as np
import pandas as pd
from typing import List, Dict, Any

class GoalsStatistics:
    """Calculates goal statistics: mean, median, standard deviation, and distributions"""

    @staticmethod
    def analyze_team_goals(historical_matches: List[Dict[str, Any]], team_name: str) -> Dict[str, Any]:
        """Compute comprehensive goal stats for a specific team"""
        goals_scored = []
        goals_conceded = []

        for m in historical_matches:
            if m.get("home_team", "").lower() == team_name.lower():
                goals_scored.append(m.get("home_goals", 0))
                goals_conceded.append(m.get("away_goals", 0))
            elif m.get("away_team", "").lower() == team_name.lower():
                goals_scored.append(m.get("away_goals", 0))
                goals_conceded.append(m.get("home_goals", 0))

        if not goals_scored:
            return {
                "team": team_name,
                "sample_size": 0,
                "mean_scored": 1.3,
                "median_scored": 1.0,
                "std_scored": 0.5,
                "mean_conceded": 1.1,
                "median_conceded": 1.0,
                "std_conceded": 0.5
            }

        arr_scored = np.array(goals_scored)
        arr_conceded = np.array(goals_conceded)

        return {
            "team": team_name,
            "sample_size": len(goals_scored),
            "mean_scored": round(float(np.mean(arr_scored)), 2),
            "median_scored": round(float(np.median(arr_scored)), 2),
            "std_scored": round(float(np.std(arr_scored)), 2),
            "mean_conceded": round(float(np.mean(arr_conceded)), 2),
            "median_conceded": round(float(np.median(arr_conceded)), 2),
            "std_conceded": round(float(np.std(arr_conceded)), 2)
        }
