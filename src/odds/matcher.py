from typing import List, Dict, Any

class EventMatcher:
    """Matches events and standardizes outcome keys across bookmakers"""

    @staticmethod
    def match_team_names(name1: str, name2: str) -> bool:
        """Fuzzy comparison of team names for matching events"""
        clean1 = name1.lower().strip().replace("fc", "").replace("cf", "").strip()
        clean2 = name2.lower().strip().replace("fc", "").replace("cf", "").strip()
        return clean1 == clean2 or clean1 in clean2 or clean2 in clean1

    @staticmethod
    def extract_best_odds(bookmakers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Extract highest available decimal odds across all bookmakers for each selection.
        Returns:
        {
          "home_win": {"odds": 2.30, "bookmaker": "Betfair"},
          "draw": {"odds": 3.80, "bookmaker": "1xBet"},
          "away_win": {"odds": 4.10, "bookmaker": "Betano"}
        }
        """
        best_odds: Dict[str, Dict[str, Any]] = {}

        for bm in bookmakers:
            bm_name = bm.get("name", "Unknown")
            odds_dict = bm.get("odds", {})
            for selection, price in odds_dict.items():
                if selection not in best_odds or price > best_odds[selection]["odds"]:
                    best_odds[selection] = {
                        "odds": float(price),
                        "bookmaker": bm_name
                    }
        return best_odds
