import pytest
from src.analyzers.surebet import SurebetAnalyzer
from src.calculators.stakes import StakeCalculator

def test_surebet_positive_arbitrage():
    """Test detection of positive arbitrage opportunity (inverse_sum < 1)"""
    # Odds: 2.30, 3.80, 4.10 -> 1/2.30 + 1/3.80 + 1/4.10 = 0.4347 + 0.2631 + 0.2439 = 0.9417 < 1.0
    event = {
        "event_id": "test_sure_001",
        "sport": "Soccer",
        "league": "Test League",
        "home_team": "Team A",
        "away_team": "Team B",
        "market": "1X2",
        "timestamp": "2026-09-10T12:00:00Z",
        "bookmakers": [
            {"name": "Bookie 1", "odds": {"home_win": 2.30, "draw": 3.40, "away_win": 3.00}},
            {"name": "Bookie 2", "odds": {"home_win": 2.10, "draw": 3.80, "away_win": 3.50}},
            {"name": "Bookie 3", "odds": {"home_win": 2.00, "draw": 3.20, "away_win": 4.10}}
        ]
    }

    opportunities = SurebetAnalyzer.analyze_event(event, default_bankroll=100.0)
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp["type"] == "surebet"
    assert opp["roi"] > 0
    assert opp["details"]["inverse_sum"] < 1.0
    assert len(opp["details"]["legs"]) == 3

def test_surebet_negative_arbitrage():
    """Test standard market with margin (no surebet opportunity)"""
    # Standard 1X2 odds with margin (inverse_sum > 1)
    event = {
        "event_id": "test_sure_002",
        "sport": "Soccer",
        "league": "Test League",
        "home_team": "Team A",
        "away_team": "Team B",
        "market": "1X2",
        "timestamp": "2026-09-10T12:00:00Z",
        "bookmakers": [
            {"name": "Bookie 1", "odds": {"home_win": 1.90, "draw": 3.20, "away_win": 3.80}}
        ]
    }

    opportunities = SurebetAnalyzer.analyze_event(event, default_bankroll=100.0)
    assert len(opportunities) == 0
