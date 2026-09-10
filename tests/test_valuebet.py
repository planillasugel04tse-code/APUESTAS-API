import pytest
from src.analyzers.value_betting import ValueBettingAnalyzer
from src.calculators.roi import ROICalculator

def test_valuebet_positive_edge():
    """Test identification of positive value bet (Market Odds > Fair Odds)"""
    # Model probability = 60% -> Fair odds = 1 / 0.60 = 1.67
    # Market odds = 2.10
    val = ROICalculator.calculate_value_edge(model_probability=0.60, bookmaker_odds=2.10)
    assert val["is_value"] is True
    assert val["fair_odds"] == 1.67
    # Edge = (0.60 * 2.10 - 1) * 100 = 26%
    assert val["edge_percentage"] == 26.0

def test_valuebet_negative_edge():
    """Test identification of negative value (Market Odds < Fair Odds)"""
    # Model probability = 40% -> Fair odds = 1 / 0.40 = 2.50
    # Market odds = 2.10
    val = ROICalculator.calculate_value_edge(model_probability=0.40, bookmaker_odds=2.10)
    assert val["is_value"] is False
    assert val["edge_percentage"] < 0
