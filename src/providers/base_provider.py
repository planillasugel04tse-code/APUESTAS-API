from abc import ABC, abstractmethod
from typing import List, Dict, Any

class OddsProvider(ABC):
    """Abstract Base Class for Odds Providers"""

    @abstractmethod
    def get_events(self) -> List[Dict[str, Any]]:
        """Fetch and return events in standardized format"""
        pass

    @abstractmethod
    def get_odds(self, event_id: str) -> List[Dict[str, Any]]:
        """Fetch odds for a specific event"""
        pass

    @abstractmethod
    def get_statistics(self, team_name: str) -> Dict[str, Any]:
        """Fetch historical statistics for a team"""
        pass
