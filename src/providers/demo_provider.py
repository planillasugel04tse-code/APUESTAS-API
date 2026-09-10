import json
from pathlib import Path
from typing import List, Dict, Any
from src.providers.base_provider import OddsProvider
from src.config import config

class DemoProvider(OddsProvider):
    """Demo Mode Odds Provider loading data from local JSON files"""

    def __init__(self, sample_odds_path: Path = config.SAMPLE_ODDS_PATH, historical_path: Path = config.HISTORICAL_MATCHES_PATH):
        self.sample_odds_path = sample_odds_path
        self.historical_path = historical_path

    def get_events(self) -> List[Dict[str, Any]]:
        """Load events from sample_odds.json"""
        if not self.sample_odds_path.exists():
            return []
        
        with open(self.sample_odds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data

    def get_odds(self, event_id: str) -> List[Dict[str, Any]]:
        """Get odds for a specific event by ID"""
        events = self.get_events()
        for event in events:
            if event["event_id"] == event_id:
                return event.get("bookmakers", [])
        return []

    def get_statistics(self, team_name: str) -> Dict[str, Any]:
        """Aggregate statistical data for a team from historical_matches.json"""
        if not self.historical_path.exists():
            return {"team": team_name, "matches_played": 0, "avg_goals": 0.0, "avg_corners": 0.0}

        with open(self.historical_path, "r", encoding="utf-8") as f:
            matches = json.load(f)

        team_matches = [
            m for m in matches 
            if m["home_team"].lower() == team_name.lower() or m["away_team"].lower() == team_name.lower()
        ]

        if not team_matches:
            return {"team": team_name, "matches_played": 0, "avg_goals": 0.0, "avg_corners": 0.0}

        total_goals = 0
        total_corners = 0
        count = len(team_matches)

        for m in team_matches:
            if m["home_team"].lower() == team_name.lower():
                total_goals += m["home_goals"]
                total_corners += m["home_corners"]
            else:
                total_goals += m["away_goals"]
                total_corners += m["away_corners"]

        return {
            "team": team_name,
            "matches_played": count,
            "avg_goals": round(total_goals / count, 2),
            "avg_corners": round(total_corners / count, 2)
        }

    def get_all_historical_matches(self) -> List[Dict[str, Any]]:
        """Retrieve raw historical matches"""
        if not self.historical_path.exists():
            return []
        with open(self.historical_path, "r", encoding="utf-8") as f:
            return json.load(f)
