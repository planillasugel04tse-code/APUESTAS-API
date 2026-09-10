import pytest
from src.analyzers.range_strategy import RangeStrategyAnalyzer

def test_range_gap_detection():
    """Test line comparison gap detection and risk assessment"""
    event = {
        "event_id": "test_range_001",
        "sport": "Soccer",
        "league": "Test League",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "market": "Corners Range",
        "timestamp": "2026-09-14T16:30:00Z",
        "bookmakers": [
            {"name": "Bookie A", "odds": {"under_7.0": 2.25}},
            {"name": "Bookie B", "odds": {"over_8.0": 2.35}}
        ]
    }
    history = [
        {"home_team": "Arsenal", "away_team": "Chelsea", "home_corners": 6, "away_corners": 4}
    ]

    opps = RangeStrategyAnalyzer.analyze_event(event, history, default_bankroll=100.0)
    assert len(opps) == 1
    opp = opps[0]
    assert opp["type"] == "range"
    assert opp["details"]["status"] == "Uncovered Gap"
    assert 7 in opp["details"]["gap_outcomes"] or 8 in opp["details"]["gap_outcomes"]

def test_range_exact_integer_gap():
    """Test integer totals can leave the exact line uncovered."""
    under = {"bookmaker": "Bookie A", "selection": "under_7.0", "type": "under", "line": 7.0, "odds": 3.00}
    over = {"bookmaker": "Bookie B", "selection": "over_7.0", "type": "over", "line": 7.0, "odds": 3.00}
    event = {
        "event_id": "test_range_002",
        "sport": "Soccer",
        "league": "Test League",
        "home_team": "Team A",
        "away_team": "Team B",
        "market": "Corners Range",
        "timestamp": "2026-09-14T16:30:00Z",
    }

    opp = RangeStrategyAnalyzer._evaluate_range_pair(event, under, over, expected_corners=8.0, default_bankroll=100.0)

    assert opp is not None
    assert opp["details"]["status"] == "Uncovered Gap"
    assert opp["details"]["gap_outcomes"] == [7]

def test_range_half_point_full_coverage():
    """Test half-point totals cover all integer outcomes with no exact gap."""
    under = {"bookmaker": "Bookie A", "selection": "under_7.5", "type": "under", "line": 7.5, "odds": 2.20}
    over = {"bookmaker": "Bookie B", "selection": "over_7.5", "type": "over", "line": 7.5, "odds": 2.20}
    event = {
        "event_id": "test_range_003",
        "sport": "Soccer",
        "league": "Test League",
        "home_team": "Team A",
        "away_team": "Team B",
        "market": "Corners Range",
        "timestamp": "2026-09-14T16:30:00Z",
    }

    opp = RangeStrategyAnalyzer._evaluate_range_pair(event, under, over, expected_corners=8.0, default_bankroll=100.0)

    assert opp is not None
    assert opp["details"]["status"] == "Fully Covered"
    assert opp["details"]["gap_outcomes"] == []
