import numpy as np
from typing import List, Dict, Any

class CornersStatistics:
    """Calculates corner statistics for teams and matches"""

    @staticmethod
    def analyze_team_corners(historical_matches: List[Dict[str, Any]], team_name: str) -> Dict[str, Any]:
        """Compute corner averages, median, and std deviation"""
        corners_taken = []
        corners_conceded = []

        for m in historical_matches:
            if m.get("home_team", "").lower() == team_name.lower():
                corners_taken.append(m.get("home_corners", 0))
                corners_conceded.append(m.get("away_corners", 0))
            elif m.get("away_team", "").lower() == team_name.lower():
                corners_taken.append(m.get("away_corners", 0))
                corners_conceded.append(m.get("home_corners", 0))

        if not corners_taken:
            return {
                "team": team_name,
                "sample_size": 0,
                "mean_corners": 5.5,
                "median_corners": 5.0,
                "std_corners": 1.5
            }

        arr_corners = np.array(corners_taken)

        return {
            "team": team_name,
            "sample_size": len(corners_taken),
            "mean_corners": round(float(np.mean(arr_corners)), 2),
            "median_corners": round(float(np.median(arr_corners)), 2),
            "std_corners": round(float(np.std(arr_corners)), 2)
        }

    @staticmethod
    def calculate_match_expected_corners(home_stats: Dict[str, Any], away_stats: Dict[str, Any]) -> float:
        """Combine team averages to estimate total match corners"""
        home_avg = home_stats.get("mean_corners", 5.0)
        away_avg = away_stats.get("mean_corners", 4.5)
        return round(home_avg + away_avg, 2)
