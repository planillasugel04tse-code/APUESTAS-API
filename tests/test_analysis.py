from betano_analyzer.analysis.markets import analyze_market
from betano_analyzer.analysis.value import expected_value, implied_probability


def test_market_margin_and_fair_probability():
    result = analyze_market([2.0, 3.0, 4.0])
    assert result.margin > 0
    assert abs(sum(result.fair_probabilities) - 1.0) < 1e-9


def test_implied_probability():
    assert implied_probability(2.0) == 0.5


def test_expected_value():
    assert expected_value(0.55, 2.0) == 0.1
